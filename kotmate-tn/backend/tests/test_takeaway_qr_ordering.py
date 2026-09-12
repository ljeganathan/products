"""Phase 26 — QR self-order for Takeaway (non-seating sections): one QR per
(location, section), every scan is an independent order (never a shared cart, unlike
a table's QR), and no real KOT ticket/stock deduction/print happens until staff
confirms via the existing "KOT + Print Bill" action.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _default_location_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/api/v1/locations", headers=headers)
    return resp.json()[0]["id"]


async def _section_id(client: AsyncClient, headers: dict, name_en: str) -> str:
    resp = await client.get("/api/v1/sections", headers=headers)
    return next(s["id"] for s in resp.json() if s["name_en"] == name_en)


async def _enable_qr_self_order(client: AsyncClient, headers: dict) -> None:
    resp = await client.patch("/api/v1/settings/qr-self-order", json={"enabled": True}, headers=headers)
    assert resp.status_code == 200, resp.text


async def _create_category(client: AsyncClient, headers: dict, name_en: str = "Mains") -> dict:
    resp = await client.post("/api/v1/categories", json={"name_en": name_en}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _create_item(client: AsyncClient, headers: dict, category_id: str, **overrides) -> dict:
    payload = {"name_en": "Meals", "category_id": category_id, "price": 200}
    payload.update(overrides)
    resp = await client.post("/api/v1/items", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _generate_section_qr(client: AsyncClient, headers: dict, section_id: str, location_id: str) -> str:
    resp = await client.post(
        f"/api/v1/sections/{section_id}/qr-code", params={"location_id": location_id}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["qr_token"]


async def _start_guest_session(client: AsyncClient, qr_token: str) -> dict:
    resp = await client.post(f"/api/v1/guest/sessions/{qr_token}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _guest_headers(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['guest_token']}"}


async def test_section_qr_generation_gated_pro_max_only_and_one_per_location(
    client: AsyncClient, tenant_admin: dict, pro_max_tenant_admin: dict
):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "Takeaway")

    lite_resp = await client.post(
        f"/api/v1/sections/{section_id}/qr-code", params={"location_id": location_id}, headers=headers
    )
    assert lite_resp.status_code == 403

    pm_headers = pro_max_tenant_admin["headers"]
    pm_location_id = await _default_location_id(client, pm_headers)
    pm_section_id = await _section_id(client, pm_headers, "Takeaway")

    resp = await client.post(
        f"/api/v1/sections/{pm_section_id}/qr-code",
        params={"location_id": pm_location_id},
        headers=pm_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["section_name_en"] == "Takeaway"
    assert body["qr_token"]

    # Idempotent — calling again returns the exact same code.
    again = await client.post(
        f"/api/v1/sections/{pm_section_id}/qr-code",
        params={"location_id": pm_location_id},
        headers=pm_headers,
    )
    assert again.status_code == 201
    assert again.json()["qr_token"] == body["qr_token"]


async def test_two_scans_of_same_takeaway_qr_never_share_a_cart(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """The core architectural difference from a table's QR: two customers scanning the
    same counter Takeaway code are two unrelated orders, never a shared one.
    """
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "Takeaway")
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_section_qr(client, headers, section_id, location_id)

    session_a = await _start_guest_session(client, qr_token)
    session_b = await _start_guest_session(client, qr_token)

    assert session_a["order_id"] is None
    assert session_b["order_id"] is None
    assert session_a["pickup_token"] != session_b["pickup_token"]
    assert session_a["table_id"] is None
    assert session_a["table_number"] is None
    assert session_a["section_name_en"] == "Takeaway"

    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=90)
    guest_a = _guest_headers(session_a)
    guest_b = _guest_headers(session_b)

    order_a = (
        await client.post(
            "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest_a
        )
    ).json()
    order_b = (
        await client.post(
            "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 2}]}, headers=guest_b
        )
    ).json()
    assert order_a["id"] != order_b["id"]
    assert len(order_a["items"]) == 1
    assert order_b["items"][0]["quantity"] == 2

    # A third rescan of the same QR is a brand-new customer, not a resume of A or B.
    session_c = await _start_guest_session(client, qr_token)
    assert session_c["order_id"] is None
    assert session_c["pickup_token"] not in (session_a["pickup_token"], session_b["pickup_token"])


async def test_takeaway_place_order_creates_no_ticket_until_staff_confirms(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "Takeaway")
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_section_qr(client, headers, section_id, location_id)
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=90)

    session = await _start_guest_session(client, qr_token)
    guest = _guest_headers(session)
    cart = await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 2}]}, headers=guest
    )
    order_id = cart.json()["id"]

    place = await client.post("/api/v1/guest/send-kot", headers=guest)
    assert place.status_code == 201, place.text
    assert place.json()["ticket_number"] == session["pickup_token"]
    assert place.json()["status"] == "pending"

    # Staff sees it as a pending row — no real ticket, token shown where a table
    # number would be, never visible on the Kitchen Display's columns (its status
    # "pending" never matches new/preparing/ready).
    tickets = await client.get("/api/v1/kot/tickets/active", headers=headers)
    pending = next(t for t in tickets.json() if t["order_id"] == order_id)
    assert pending["is_pending_takeaway"] is True
    assert pending["pickup_token"] == session["pickup_token"]
    assert pending["status"] == "pending"
    assert pending["table_number"] is None

    # Staff confirms via the existing combined "KOT + Print Bill" action — this is the
    # moment the real ticket is created, stock is deducted, and the bill is finalized.
    confirm = await client.post(
        f"/api/v1/orders/{order_id}/kot-and-bill",
        json={"order_id": order_id, "payments": [{"method": "cash", "amount": 180.0}]},
        headers=headers,
    )
    assert confirm.status_code == 201, confirm.text

    after = await client.get("/api/v1/kot/tickets/active", headers=headers)
    real_ticket = next(t for t in after.json() if t["order_id"] == order_id)
    assert real_ticket["is_pending_takeaway"] is False
    assert real_ticket["pickup_token"] == session["pickup_token"]
    assert real_ticket["order_billed_via_kot"] is True


async def test_clearing_a_pending_takeaway_order_deletes_it(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "Takeaway")
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_section_qr(client, headers, section_id, location_id)
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=90)

    session = await _start_guest_session(client, qr_token)
    guest = _guest_headers(session)
    cart = await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )
    order_id = cart.json()["id"]
    await client.post("/api/v1/guest/send-kot", headers=guest)

    clear = await client.post(f"/api/v1/kot/pending-takeaway/{order_id}/clear", headers=headers)
    assert clear.status_code == 204, clear.text

    tickets = await client.get("/api/v1/kot/tickets/active", headers=headers)
    assert not any(t["order_id"] == order_id for t in tickets.json())

    # The guest's own session has ended — their tab shows "please rescan" now.
    stale_cart = await client.get("/api/v1/guest/cart", headers=guest)
    assert stale_cart.status_code == 404


async def test_cannot_clear_an_already_ticketed_takeaway_order(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "Takeaway")
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_section_qr(client, headers, section_id, location_id)
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=90)

    session = await _start_guest_session(client, qr_token)
    guest = _guest_headers(session)
    cart = await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )
    order_id = cart.json()["id"]
    await client.post("/api/v1/guest/send-kot", headers=guest)
    confirm = await client.post(
        f"/api/v1/orders/{order_id}/kot-and-bill",
        json={"order_id": order_id, "payments": [{"method": "cash", "amount": 90.0}]},
        headers=headers,
    )
    assert confirm.status_code == 201, confirm.text

    clear = await client.post(f"/api/v1/kot/pending-takeaway/{order_id}/clear", headers=headers)
    assert clear.status_code == 400


async def test_takeaway_guest_can_request_bill_and_staff_sees_it_claimed(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "Takeaway")
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_section_qr(client, headers, section_id, location_id)
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=90)

    session = await _start_guest_session(client, qr_token)
    guest = _guest_headers(session)
    cart = await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )
    order_id = cart.json()["id"]

    preview = await client.get("/api/v1/guest/bill-preview", headers=guest)
    assert preview.status_code == 200, preview.text

    claim = await client.post("/api/v1/guest/request-bill", headers=guest)
    assert claim.status_code == 200
    assert claim.json()["status"] == "payment_claimed"

    tickets = await client.get("/api/v1/kot/tickets/active", headers=headers)
    pending = next(t for t in tickets.json() if t["order_id"] == order_id)
    assert pending["guest_payment_claimed"] is True
