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


async def test_lite_tenant_kot_deduction_still_works_unconditionally(
    client: AsyncClient, tenant_admin: dict
):
    """Lite predates plan-gating on track_inventory (CLAUDE.md §11) — "zero behavior
    change for Lite" per this feature's acceptance criteria, including the new ledger.
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

    resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert resp.status_code == 201

    items = (await client.get("/api/v1/items", headers=headers)).json()
    updated = next(i for i in items if i["id"] == item["id"])
    assert updated["available_qty"] == 7

    rows = await _ledger_rows(tenant_id, item["id"])
    assert len(rows) == 1
    assert rows[0].reason == "kot_deduction"
    assert rows[0].change_qty == -3
    assert rows[0].reference_order_id == uuid.UUID(order["id"])
    assert rows[0].location_id == uuid.UUID(location_id)


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
