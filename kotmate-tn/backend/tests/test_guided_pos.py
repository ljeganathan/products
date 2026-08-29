import pytest
from httpx import AsyncClient

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


async def _waiter_headers(client: AsyncClient, admin_headers: dict, local_handle: str = "w1") -> dict:
    waiter = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": local_handle, "name": "W1", "role": "waiter", "password": "password123"},
            headers=admin_headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter["user_id"], "password": "password123"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# --- Settings + /auth/me -----------------------------------------------------------


async def test_pos_layout_setting_defaults_and_updates(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["pos_layout"] == "default"
    assert me["waiter_mandatory_enabled"] is True

    resp = await client.patch("/api/v1/settings/pos-layout", json={"pos_layout": "guided"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["pos_layout"] == "guided"

    me_after = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me_after["pos_layout"] == "guided"


async def test_pos_layout_setting_rejects_invalid_value(client: AsyncClient, tenant_admin: dict):
    resp = await client.patch(
        "/api/v1/settings/pos-layout", json={"pos_layout": "bogus"}, headers=tenant_admin["headers"]
    )
    assert resp.status_code == 422


async def test_pos_layout_setting_tenant_admin_only(client: AsyncClient, tenant_admin: dict):
    waiter_headers = await _waiter_headers(client, tenant_admin["headers"])
    resp = await client.patch(
        "/api/v1/settings/pos-layout", json={"pos_layout": "guided"}, headers=waiter_headers
    )
    assert resp.status_code == 403


async def test_waiter_mandatory_setting_updates(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    resp = await client.patch(
        "/api/v1/settings/waiter-mandatory", json={"enabled": False}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["waiter_mandatory_enabled"] is False


# --- Combined "KOT + Bill" route -----------------------------------------------------


async def test_kot_and_bill_creates_one_ticket_and_one_bill_atomically(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    takeaway_id = await _section_id(client, headers, "Takeaway")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)
    order = await _create_order(
        client, headers, location_id, takeaway_id, [{"item_id": item["id"], "quantity": 2}]
    )

    resp = await client.post(
        f"/api/v1/orders/{order['id']}/kot-and-bill",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 200.0}]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "finalized"
    assert body["grand_total"] == 200.0
    assert body["kot_ticket_number"]

    # Order is billed exactly like any other bill.
    refetched = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert refetched["status"] == "billed"

    # Exactly one ticket exists for this order, and it stays visible even though the
    # order is billed (order_billed_via_kot narrow exception).
    tickets = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    matching = [t for t in tickets if t["order_id"] == order["id"]]
    assert len(matching) == 1
    assert matching[0]["ticket_number"] == body["kot_ticket_number"]
    assert matching[0]["status"] == "new"

    # Once marked ready, it drops off same as any other fulfilled ticket.
    ready = await client.patch(
        f"/api/v1/kot/tickets/{matching[0]['id']}/status", json={"status": "ready"}, headers=headers
    )
    assert ready.status_code == 200
    tickets_after_ready = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    assert not any(t["order_id"] == order["id"] for t in tickets_after_ready)


async def test_kot_and_bill_rejects_waiter_token(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    takeaway_id = await _section_id(client, headers, "Takeaway")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)
    order = await _create_order(
        client, headers, location_id, takeaway_id, [{"item_id": item["id"], "quantity": 1}]
    )
    waiter_headers = await _waiter_headers(client, headers)

    resp = await client.post(
        f"/api/v1/orders/{order['id']}/kot-and-bill",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 100.0}]},
        headers=waiter_headers,
    )
    assert resp.status_code == 403


async def test_kot_and_bill_blocked_on_lite_plan(client: AsyncClient, tenant_admin: dict):
    """No KDS feature (Lite/Pro) — the combined route must reject the same way the
    plain KOT-send route does, rather than firing a kitchen ticket for a tenant with no
    KOT screen at all.
    """
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    takeaway_id = await _section_id(client, headers, "Takeaway")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)
    order = await _create_order(
        client, headers, location_id, takeaway_id, [{"item_id": item["id"], "quantity": 1}]
    )

    resp = await client.post(
        f"/api/v1/orders/{order['id']}/kot-and-bill",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 100.0}]},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_kot_and_bill_rolls_back_fully_on_payment_mismatch(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """If the bill half fails (e.g. payments don't add up), the whole transaction must
    roll back — no orphaned KOT ticket left behind for an order that was never billed.
    """
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    takeaway_id = await _section_id(client, headers, "Takeaway")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)
    order = await _create_order(
        client, headers, location_id, takeaway_id, [{"item_id": item["id"], "quantity": 1}]
    )

    resp = await client.post(
        f"/api/v1/orders/{order['id']}/kot-and-bill",
        # Grand total is 100 — this payment total (50) deliberately doesn't match.
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 50.0}]},
        headers=headers,
    )
    assert resp.status_code == 400

    refetched = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert refetched["status"] == "open"
    assert refetched["items"][0]["is_kot_sent"] is False

    tickets = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    assert not any(t["order_id"] == order["id"] for t in tickets)
