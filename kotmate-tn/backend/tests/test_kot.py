import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db.session import async_session_maker
from app.models import Order

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


async def test_send_kot_creates_ticket_and_marks_items_sent(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=50)
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 2}]
    )

    resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["ticket_number"]
    assert body["status"] == "new"
    assert body["section_name_en"] == "AC"
    assert body["printed"] is False  # no printer registered

    refetched = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert refetched["items"][0]["is_kot_sent"] is True


async def test_repeat_kot_only_sends_new_items(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item_a = await _create_item(client, headers, category["id"], name_en="Item A", price=50)
    item_b = await _create_item(client, headers, category["id"], name_en="Item B", price=30)
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item_a["id"], "quantity": 1}]
    )

    first = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert first.status_code == 201

    # No new items yet — repeat send must be rejected, not silently re-fire.
    no_new = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert no_new.status_code == 400

    await client.patch(
        f"/api/v1/orders/{order['id']}",
        json={"items": [{"item_id": item_a["id"], "quantity": 1}, {"item_id": item_b["id"], "quantity": 2}]},
        headers=headers,
    )

    second = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert second.status_code == 201
    assert second.json()["ticket_number"] != first.json()["ticket_number"]

    tickets = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    second_ticket = next(t for t in tickets if t["ticket_number"] == second.json()["ticket_number"])
    assert [i["name_en"] for i in second_ticket["items"]] == ["Item B"]

    first_ticket = next(t for t in tickets if t["ticket_number"] == first.json()["ticket_number"])
    assert [i["name_en"] for i in first_ticket["items"]] == ["Item A"]


async def test_stock_decrement_floors_at_zero(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    # stock_management_enabled defaults off on Pro/Pro Max (opt-in soft-disable switch,
    # CLAUDE.md §11 extension) — Lite has no such gate, which is why this fixture needs
    # the explicit PATCH that a Lite-tenant version of this test never did.
    await client.patch("/api/v1/settings/stock-management", json={"enabled": True}, headers=headers)
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(
        client, headers, category["id"], price=20, track_inventory=True, available_qty=2
    )
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 5}]
    )

    resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert resp.status_code == 201

    refreshed_item = (await client.get("/api/v1/items", headers=headers)).json()
    updated = next(i for i in refreshed_item if i["id"] == item["id"])
    assert updated["available_qty"] == 0


async def test_untracked_item_stock_untouched(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=20)
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 3}]
    )

    resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert resp.status_code == 201

    items = (await client.get("/api/v1/items", headers=headers)).json()
    updated = next(i for i in items if i["id"] == item["id"])
    assert updated["available_qty"] is None


async def test_active_tickets_drop_once_order_billed(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=20)
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )
    await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)

    tickets_before = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    assert any(t["order_id"] == order["id"] for t in tickets_before)

    # Phase 09 (billing) doesn't exist yet — simulate the order being billed directly.
    async with async_session_maker() as session:
        await session.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))
        db_order = (await session.execute(select(Order).where(Order.id == order["id"]))).scalar_one()
        db_order.status = "billed"
        await session.commit()

    tickets_after = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    assert not any(t["order_id"] == order["id"] for t in tickets_after)


async def test_lite_tenant_kot_endpoints_blocked_by_tier_gate(client: AsyncClient, tenant_admin: dict):
    """The whole KOT screen/workflow — not just physical printing — is Pro Max only
    (production feedback round 2, `kds` feature flag flipped off for Lite/Pro). A Lite
    tenant can't reach any /kot endpoint at all now, regardless of a registered printer.
    """
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=20)
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )

    await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Kitchen Printer",
            "target": "kot",
            "printer_type": "thermal",
            "connection_type": "network",
        },
        headers=headers,
    )

    send_resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert send_resp.status_code == 403

    tickets_resp = await client.get("/api/v1/kot/tickets/active", headers=headers)
    assert tickets_resp.status_code == 403


async def test_pro_max_dispatches_print_only_with_registered_printer(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=20)

    order_without_printer = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )
    no_printer_resp = await client.post(
        "/api/v1/kot", json={"order_id": order_without_printer["id"]}, headers=headers
    )
    assert no_printer_resp.json()["printed"] is False

    await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Kitchen Printer",
            "target": "kot",
            "printer_type": "thermal",
            # usb rather than network — this test exercises the printer-registered
            # dispatch flow itself, not real network reachability.
            "connection_type": "usb",
        },
        headers=headers,
    )

    order_with_printer = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )
    printed_resp = await client.post(
        "/api/v1/kot", json={"order_id": order_with_printer["id"]}, headers=headers
    )
    assert printed_resp.json()["printed"] is True


async def test_kitchen_role_blocked_from_sending_kot(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    kot_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "kot01", "name": "Kitchen", "role": "kitchen", "password": "password123"},
            headers=headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": kot_user["user_id"], "password": "password123"}
    )
    kitchen_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.post(
        "/api/v1/kot", json={"order_id": "00000000-0000-0000-0000-000000000000"}, headers=kitchen_headers
    )
    assert resp.status_code == 403


async def test_ticket_status_transition_and_role_gating(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=20)
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )
    ticket = (await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)).json()

    kot_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "kot02", "name": "Kitchen2", "role": "kitchen", "password": "password123"},
            headers=headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": kot_user["user_id"], "password": "password123"}
    )
    kitchen_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # pos_user/waiter cannot update ticket status — only kitchen/tenant_admin.
    waiter = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w1", "name": "W1", "role": "waiter", "password": "password123"},
            headers=headers,
        )
    ).json()
    waiter_login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {waiter_login.json()['access_token']}"}
    blocked = await client.patch(
        f"/api/v1/kot/tickets/{ticket['id']}/status", json={"status": "preparing"}, headers=waiter_headers
    )
    assert blocked.status_code == 403

    preparing = await client.patch(
        f"/api/v1/kot/tickets/{ticket['id']}/status", json={"status": "preparing"}, headers=kitchen_headers
    )
    assert preparing.status_code == 200
    assert preparing.json()["status"] == "preparing"

    ready = await client.patch(
        f"/api/v1/kot/tickets/{ticket['id']}/status", json={"status": "ready"}, headers=headers
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


async def test_takeaway_ticket_has_no_table_number(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    takeaway_id = await _section_id(client, headers, "Takeaway")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=20)
    order = await _create_order(
        client, headers, location_id, takeaway_id, [{"item_id": item["id"], "quantity": 1}]
    )

    resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    body = resp.json()
    assert body["table_number"] is None
    assert body["section_name_en"] == "Takeaway"
