"""Takeaway QR orders: the guest chooses to pay online (no ticket until the payment is
verified) or in cash at the counter (the order waits on the KOT Tickets list until staff
confirm it). The gateway is replaced with the in-memory fake from test_online_payments.
"""

import pytest
from httpx import AsyncClient

from tests.test_online_payments import _configure, fake_gateway  # noqa: F401 - fixture
from tests.test_takeaway_qr_ordering import (
    _create_category,
    _create_item,
    _default_location_id,
    _enable_qr_self_order,
    _generate_section_qr,
    _guest_headers,
    _section_id,
    _set_guest_profile,
    _start_guest_session,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _takeaway_cart(client: AsyncClient, headers: dict, price: int = 90):
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "Takeaway")
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_section_qr(client, headers, section_id, location_id)
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=price)
    session = await _start_guest_session(client, qr_token)
    guest = _guest_headers(session)
    await _set_guest_profile(client, guest)
    cart = await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 2}]}, headers=guest
    )
    assert cart.status_code == 200, cart.text
    return guest, session, cart.json()["id"]


async def test_online_choice_is_refused_when_online_payment_is_off(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    guest, _, _ = await _takeaway_cart(client, headers)
    resp = await client.post("/api/v1/guest/send-kot", json={"payment_method": "online"}, headers=guest)
    assert resp.status_code == 400
    assert "isn't available" in resp.json()["detail"]


async def test_online_order_creates_no_ticket_until_paid(
    client: AsyncClient, pro_max_tenant_admin: dict, fake_gateway  # noqa: F811
):
    headers = pro_max_tenant_admin["headers"]
    await _configure(client, headers)
    guest, session, order_id = await _takeaway_cart(client, headers, price=90)

    placed = await client.post("/api/v1/guest/send-kot", json={"payment_method": "online"}, headers=guest)
    assert placed.status_code == 201, placed.text
    assert placed.json()["status"] == "awaiting_payment"
    assert placed.json()["ticket_number"] == ""

    # Not on the POS list yet: no ticket and nothing for the counter to confirm.
    tickets = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    assert not any(t["order_id"] == order_id for t in tickets)

    created = (await client.post("/api/v1/guest/payments/create", headers=guest)).json()
    fake_gateway.pay(created["provider_order_id"], 18000)
    paid = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert paid.json()["status"] == "paid"

    # The verified payment fires the ticket, straight to the kitchen (not a pending row).
    tickets = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    ticket = next(t for t in tickets if t["order_id"] == order_id)
    assert ticket["is_pending_takeaway"] is False
    assert ticket["status"] == "new"
    assert ticket["pickup_token"] == session["pickup_token"]


async def test_cash_order_waits_on_pos_list_and_pick_is_recorded(
    client: AsyncClient, pro_max_tenant_admin: dict, fake_gateway  # noqa: F811
):
    headers = pro_max_tenant_admin["headers"]
    await _configure(client, headers)
    guest, session, order_id = await _takeaway_cart(client, headers)

    placed = await client.post("/api/v1/guest/send-kot", json={"payment_method": "cash"}, headers=guest)
    assert placed.status_code == 201, placed.text
    assert placed.json()["status"] == "pending"
    assert placed.json()["ticket_number"] == session["pickup_token"]

    tickets = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    pending = next(t for t in tickets if t["order_id"] == order_id)
    assert pending["is_pending_takeaway"] is True
    assert pending["pickup_token"] == session["pickup_token"]

    # The session response carries the choice (a profile PATCH returns the full session).
    refreshed = await client.patch(
        "/api/v1/guest/sessions/me",
        json={"customer_name": "Test Guest", "customer_phone": "9876543210"},
        headers=guest,
    )
    assert refreshed.json()["takeaway_payment"] == "cash"

    # Once it's a cash order, it can't be switched to online.
    switch = await client.post("/api/v1/guest/send-kot", json={"payment_method": "online"}, headers=guest)
    assert switch.status_code == 409


async def test_unpaid_online_choice_can_still_switch_to_cash(
    client: AsyncClient, pro_max_tenant_admin: dict, fake_gateway  # noqa: F811
):
    headers = pro_max_tenant_admin["headers"]
    await _configure(client, headers)
    guest, _, order_id = await _takeaway_cart(client, headers)

    await client.post("/api/v1/guest/send-kot", json={"payment_method": "online"}, headers=guest)
    switched = await client.post("/api/v1/guest/send-kot", json={"payment_method": "cash"}, headers=guest)
    assert switched.status_code == 201, switched.text
    assert switched.json()["status"] == "pending"

    tickets = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    assert any(t["order_id"] == order_id and t["is_pending_takeaway"] for t in tickets)


async def test_send_without_a_choice_keeps_the_previous_behaviour(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    guest, _, order_id = await _takeaway_cart(client, headers)
    placed = await client.post("/api/v1/guest/send-kot", headers=guest)
    assert placed.status_code == 201, placed.text
    assert placed.json()["status"] == "pending"
    tickets = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    assert any(t["order_id"] == order_id and t["is_pending_takeaway"] for t in tickets)
