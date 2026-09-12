import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db.session import async_session_maker
from app.models import Item, StockLedger

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _default_location_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/api/v1/locations", headers=headers)
    return resp.json()[0]["id"]


async def _section_id(client: AsyncClient, headers: dict, name_en: str) -> str:
    resp = await client.get("/api/v1/sections", headers=headers)
    return next(s["id"] for s in resp.json() if s["name_en"] == name_en)


async def _create_category(client: AsyncClient, headers: dict, name_en: str = "Mains") -> dict:
    resp = await client.post("/api/v1/categories", json={"name_en": name_en}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _create_item(client: AsyncClient, headers: dict, category_id: str, **overrides) -> dict:
    payload = {"name_en": "Meals", "category_id": category_id, "price": 100}
    payload.update(overrides)
    resp = await client.post("/api/v1/items", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_order(
    client: AsyncClient, headers: dict, location_id: str, section_id: str, items: list[dict]
) -> dict:
    resp = await client.post(
        "/api/v1/orders",
        json={"location_id": location_id, "section_id": section_id, "items": items},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _ledger_rows(tenant_id: str, item_id: str) -> list[StockLedger]:
    async with async_session_maker() as session:
        await session.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))
        rows = (
            await session.execute(
                select(StockLedger).where(
                    StockLedger.tenant_id == uuid.UUID(tenant_id), StockLedger.item_id == uuid.UUID(item_id)
                )
            )
        ).scalars().all()
    return list(rows)


async def _enable_stock_management(client: AsyncClient, headers: dict, enabled: bool = True) -> None:
    resp = await client.patch("/api/v1/settings/stock-management", json={"enabled": enabled}, headers=headers)
    assert resp.status_code == 200, resp.text


async def test_lite_tenant_kot_send_blocked_by_tier_gate(client: AsyncClient, tenant_admin: dict):
    """KOT (screen + send) is Pro Max only (production feedback round 2) — a Lite
    tenant can no longer reach `/kot` at all, so stock tracking for Lite now only ever
    happens via the direct-bill deduction path (see
    test_direct_bill_deducts_stock_when_never_kot_sent), never kot_deduction.
    """
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=20, track_inventory=True, available_qty=10
    )
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 3}]
    )

    resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert resp.status_code == 403


async def test_pro_max_kot_deduction_skipped_when_toggle_off(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    tenant_id = pro_max_tenant_admin["tenant"]["id"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=20, track_inventory=True, available_qty=10
    )
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 3}]
    )

    # Toggle defaults off (migration default false) — never explicitly enabled here.
    resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert resp.status_code == 201

    items = (await client.get("/api/v1/items", headers=headers)).json()
    updated = next(i for i in items if i["id"] == item["id"])
    assert updated["available_qty"] == 10, "toggle off -> no deduction, count untouched"
    assert await _ledger_rows(tenant_id, item["id"]) == []


async def test_pro_max_kot_deduction_fires_once_toggle_enabled(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    tenant_id = pro_max_tenant_admin["tenant"]["id"]
    await _enable_stock_management(client, headers, True)
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=20, track_inventory=True, available_qty=10
    )
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 4}]
    )

    resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert resp.status_code == 201

    items = (await client.get("/api/v1/items", headers=headers)).json()
    updated = next(i for i in items if i["id"] == item["id"])
    assert updated["available_qty"] == 6

    rows = await _ledger_rows(tenant_id, item["id"])
    assert len(rows) == 1
    assert rows[0].reason == "kot_deduction"
    assert rows[0].change_qty == -4


async def test_restock_and_manual_edit_write_distinct_ledger_reasons(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    tenant_id = pro_max_tenant_admin["tenant"]["id"]
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=20, track_inventory=True, available_qty=5
    )

    restock = await client.patch(
        f"/api/v1/items/{item['id']}/restock", json={"available_qty": 20}, headers=headers
    )
    assert restock.status_code == 200, restock.text
    assert restock.json()["available_qty"] == 20

    manual_edit = await client.patch(
        f"/api/v1/items/{item['id']}", json={"available_qty": 15}, headers=headers
    )
    assert manual_edit.status_code == 200, manual_edit.text
    assert manual_edit.json()["available_qty"] == 15

    rows = {r.reason: r for r in await _ledger_rows(tenant_id, item["id"])}
    assert rows["restock"].change_qty == 15  # 5 -> 20
    assert rows["manual_set"].change_qty == -5  # 20 -> 15


async def test_stock_management_tab_blocked_on_lite(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    resp = await client.get("/api/v1/stock/items", headers=headers)
    assert resp.status_code == 403


async def test_stock_management_tab_blocked_when_toggle_off_on_pro_max(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    resp = await client.get("/api/v1/stock/items", headers=headers)
    assert resp.status_code == 403


async def test_stock_management_tab_works_on_pro_max_when_enabled(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    await _enable_stock_management(client, headers, True)
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=50)

    list_resp = await client.get("/api/v1/stock/items", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    assert any(i["id"] == item["id"] for i in list_resp.json())

    update_resp = await client.patch(
        f"/api/v1/stock/items/{item['id']}", json={"available_qty": 25}, headers=headers
    )
    assert update_resp.status_code == 200, update_resp.text
    body = update_resp.json()
    assert body["available_qty"] == 25
    # Entering a quantity turns tracking on for that item, even though it wasn't
    # opted in via Item Master's checkbox first.
    assert body["track_inventory"] is True

    rows = await _ledger_rows(pro_max_tenant_admin["tenant"]["id"], item["id"])
    assert len(rows) == 1
    assert rows[0].reason == "manual_set"
    assert rows[0].change_qty == 25


async def _create_staff_headers(client: AsyncClient, admin_headers: dict, role: str, handle: str) -> dict:
    user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": handle, "name": handle, "role": role, "password": "password123"},
            headers=admin_headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": user["user_id"], "password": "password123"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_cashier_can_use_stock_management_standalone_page(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Stock Management moved out from being a KOT-screen-only tab to its own main-nav
    page reachable by Admin and Cashier (production feedback) — Cashier previously had
    no access to these endpoints at all (tenant_admin/kitchen only).
    """
    admin_headers = pro_max_tenant_admin["headers"]
    await _enable_stock_management(client, admin_headers, True)
    category = await _create_category(client, admin_headers)
    item = await _create_item(client, admin_headers, category["id"], price=50)

    cashier_headers = await _create_staff_headers(client, admin_headers, "pos_user", "cashier01")

    list_resp = await client.get("/api/v1/stock/items", headers=cashier_headers)
    assert list_resp.status_code == 200, list_resp.text
    assert any(i["id"] == item["id"] for i in list_resp.json())

    update_resp = await client.patch(
        f"/api/v1/stock/items/{item['id']}", json={"available_qty": 40}, headers=cashier_headers
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["available_qty"] == 40


async def test_calculate_for_me_conversion_is_remembered_for_next_restock(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """The "Calculate for Me" popup's per-item conversion (e.g. "500 g used per Chicken
    Biryani") persists on the item so the next restock pre-fills it instead of asking
    the cashier to re-derive the same number every time — additive, so an item that
    never uses the calculator (a plain "Type Amount" save) simply never gets these
    fields touched.
    """
    headers = pro_max_tenant_admin["headers"]
    await _enable_stock_management(client, headers, True)
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=50)

    # Brand-new item has never used the calculator.
    before = await client.get("/api/v1/stock/items", headers=headers)
    before_row = next(i for i in before.json() if i["id"] == item["id"])
    assert before_row["stock_calc_qty"] is None
    assert before_row["stock_calc_unit"] is None

    # 100 kg bought / 500 g per Chicken Biryani = 200 — the calculator's own PATCH
    # sends both the computed available_qty and the conversion it was derived from.
    calc_resp = await client.patch(
        f"/api/v1/stock/items/{item['id']}",
        json={"available_qty": 200, "stock_calc_qty": 500, "stock_calc_unit": "g"},
        headers=headers,
    )
    assert calc_resp.status_code == 200, calc_resp.text
    assert calc_resp.json()["stock_calc_qty"] == 500
    assert calc_resp.json()["stock_calc_unit"] == "g"

    # A later plain "Type Amount" save (no calc fields sent) must not wipe the
    # remembered conversion out from under the next "Calculate for Me" open.
    plain_resp = await client.patch(
        f"/api/v1/stock/items/{item['id']}", json={"available_qty": 210}, headers=headers
    )
    assert plain_resp.status_code == 200, plain_resp.text
    assert plain_resp.json()["available_qty"] == 210
    assert plain_resp.json()["stock_calc_qty"] == 500
    assert plain_resp.json()["stock_calc_unit"] == "g"

    after = await client.get("/api/v1/stock/items", headers=headers)
    after_row = next(i for i in after.json() if i["id"] == item["id"])
    assert after_row["stock_calc_qty"] == 500
    assert after_row["stock_calc_unit"] == "g"


async def test_waiter_still_blocked_from_stock_management(client: AsyncClient, pro_max_tenant_admin: dict):
    """The Cashier carve-out above must not widen to every staff role — a waiter still
    has no legitimate reason to touch stock counts.
    """
    admin_headers = pro_max_tenant_admin["headers"]
    await _enable_stock_management(client, admin_headers, True)
    waiter_headers = await _create_staff_headers(client, admin_headers, "waiter", "waiter01")

    resp = await client.get("/api/v1/stock/items", headers=waiter_headers)
    assert resp.status_code == 403


async def test_stock_management_tab_blank_qty_stops_tracking(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Saving the Stock Management tab's qty box blank (available_qty: null) is the
    reverse of typing a quantity — it stops tracking the item entirely, so a tenant can
    remove an item from stock tracking (e.g. it ran out, got flagged out-of-stock in
    POS, and they no longer want to restock/track it) without being forced to leave a
    stale 0 behind.
    """
    headers = pro_max_tenant_admin["headers"]
    tenant_id = pro_max_tenant_admin["tenant"]["id"]
    await _enable_stock_management(client, headers, True)
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=50, track_inventory=True, available_qty=0
    )

    clear_resp = await client.patch(
        f"/api/v1/stock/items/{item['id']}", json={"available_qty": None}, headers=headers
    )
    assert clear_resp.status_code == 200, clear_resp.text
    body = clear_resp.json()
    assert body["available_qty"] is None
    assert body["track_inventory"] is False

    # The item goes back to reading exactly like one that was never tracked — confirmed
    # via Item Master, not just the Stock Management tab's own response.
    items = (await client.get("/api/v1/items", headers=headers)).json()
    updated = next(i for i in items if i["id"] == item["id"])
    assert updated["available_qty"] is None
    assert updated["track_inventory"] is False

    rows = await _ledger_rows(tenant_id, item["id"])
    assert len(rows) == 1
    assert rows[0].reason == "manual_set"
    assert rows[0].change_qty == 0  # was already at 0 before clearing


async def test_settings_toggle_blocked_on_lite(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    resp = await client.patch("/api/v1/settings/stock-management", json={"enabled": True}, headers=headers)
    assert resp.status_code == 403


async def test_toggling_off_never_clears_existing_stock_config(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Soft-disable only — turning the tenant switch off/on again must restore the
    exact same track_inventory/available_qty a tenant_admin already configured.
    """
    headers = pro_max_tenant_admin["headers"]
    await _enable_stock_management(client, headers, True)
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=20, track_inventory=True, available_qty=9
    )

    await _enable_stock_management(client, headers, False)
    items_while_off = (await client.get("/api/v1/items", headers=headers)).json()
    still_configured = next(i for i in items_while_off if i["id"] == item["id"])
    assert still_configured["track_inventory"] is True
    assert still_configured["available_qty"] == 9

    await _enable_stock_management(client, headers, True)
    items_after = (await client.get("/api/v1/items", headers=headers)).json()
    restored = next(i for i in items_after if i["id"] == item["id"])
    assert restored["available_qty"] == 9


async def test_untracked_item_unaffected_by_manual_set(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=20)
    assert item["track_inventory"] is False
    assert item["available_qty"] is None


async def test_item_response_includes_track_inventory_field(client: AsyncClient, tenant_admin: dict):
    """Confirms Item.track_inventory column still round-trips through the general item
    endpoints untouched by the Phase 21+ stock_ledger refactor.
    """
    headers = tenant_admin["headers"]
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=20)
    async with async_session_maker() as session:
        await session.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))
        row = (await session.execute(select(Item).where(Item.id == uuid.UUID(item["id"])))).scalar_one()
    assert row.track_inventory is False


async def test_direct_bill_deducts_stock_when_never_kot_sent(client: AsyncClient, tenant_admin: dict):
    """A cashier can finalize a bill straight from the cart without ever sending it to
    the kitchen (a quick walk-in sale) — that line never goes through kot_service.send_kot,
    so bill_service.finalize_bill must deduct it directly, or the item's stock would
    never decrement at all.
    """
    headers = tenant_admin["headers"]
    tenant_id = tenant_admin["tenant"]["id"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=20, track_inventory=True, available_qty=10
    )
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 3}]
    )

    resp = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 60.0}]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    bill_id = resp.json()["id"]

    items = (await client.get("/api/v1/items", headers=headers)).json()
    updated = next(i for i in items if i["id"] == item["id"])
    assert updated["available_qty"] == 7

    rows = await _ledger_rows(tenant_id, item["id"])
    assert len(rows) == 1
    assert rows[0].reason == "bill_deduction"
    assert rows[0].change_qty == -3
    assert rows[0].reference_bill_id == uuid.UUID(bill_id)
    assert rows[0].location_id == uuid.UUID(location_id)


async def test_kot_sent_item_not_double_deducted_at_bill_time(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    tenant_id = pro_max_tenant_admin["tenant"]["id"]
    await _enable_stock_management(client, headers, True)
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=20, track_inventory=True, available_qty=10
    )
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 3}]
    )

    kot_resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert kot_resp.status_code == 201

    bill_resp = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 60.0}]},
        headers=headers,
    )
    assert bill_resp.status_code == 201, bill_resp.text

    items = (await client.get("/api/v1/items", headers=headers)).json()
    updated = next(i for i in items if i["id"] == item["id"])
    # Deducted once at KOT-send (10 -> 7), NOT again at bill time.
    assert updated["available_qty"] == 7

    rows = await _ledger_rows(tenant_id, item["id"])
    assert len(rows) == 1
    assert rows[0].reason == "kot_deduction"


async def test_direct_bill_deduction_floors_at_zero(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=20, track_inventory=True, available_qty=2
    )
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 5}]
    )

    resp = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 100.0}]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    items = (await client.get("/api/v1/items", headers=headers)).json()
    updated = next(i for i in items if i["id"] == item["id"])
    assert updated["available_qty"] == 0


async def test_direct_bill_deduction_skipped_when_stock_tracking_disabled(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Mirrors the KOT-send gate — Pro Max with the tenant switch off should not deduct
    stock at bill time either, even for a directly-billed (never KOT-sent) line.
    """
    headers = pro_max_tenant_admin["headers"]
    tenant_id = pro_max_tenant_admin["tenant"]["id"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=20, track_inventory=True, available_qty=10
    )
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 3}]
    )

    resp = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 60.0}]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    items = (await client.get("/api/v1/items", headers=headers)).json()
    updated = next(i for i in items if i["id"] == item["id"])
    assert updated["available_qty"] == 10
    assert await _ledger_rows(tenant_id, item["id"]) == []
