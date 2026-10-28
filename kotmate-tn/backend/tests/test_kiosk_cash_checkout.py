"""Kiosk cash checkout (production request): the menu is the kiosk's first screen with
no profile gate, and only choosing how to pay requires name/phone. Paying online still
finalizes the bill + fires the kitchen ticket together once the payment is verified
(unchanged, covered by test_online_payments.py) — paying cash instead finalizes and
prints the bill immediately but holds the kitchen ticket back for a POS operator to
approve, which this file covers end to end.
"""

import io

import pytest
from httpx import AsyncClient

from tests.test_guest_ordering import (
    _create_category,
    _create_item,
    _default_location_id,
    _enable_qr_self_order,
    _guest_headers,
    _section_id,
    _set_guest_profile,
)
from tests.test_online_payments import _start_kiosk

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _kiosk_cart(client: AsyncClient, headers: dict, price: int = 90):
    await _enable_qr_self_order(client, headers)
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "Takeaway")
    session = await _start_kiosk(client, headers, location_id, section_id)
    guest = _guest_headers(session)
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=price)
    cart = await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )
    assert cart.status_code == 200, cart.text
    return guest


async def test_kiosk_session_exposes_the_uploaded_welcome_image(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    await _enable_qr_self_order(client, headers)
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "Takeaway")

    no_image = await _start_kiosk(client, headers, location_id, section_id)
    assert no_image["kiosk_welcome_image_url"] is None

    fake_png = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    uploaded = await client.post(
        f"/api/v1/settings/hotel-master/{location_id}/kiosk-image",
        files={"file": ("welcome.png", fake_png, "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 200, uploaded.text

    with_image = await _start_kiosk(client, headers, location_id, section_id)
    assert with_image["kiosk_welcome_image_url"] == uploaded.json()["kiosk_welcome_image_url"]


async def test_kiosk_cart_works_with_no_profile_set(client: AsyncClient, pro_max_tenant_admin: dict):
    """Production request: the item menu is the kiosk's first screen — a guest can
    browse and build a cart with no name/phone on file at all.
    """
    headers = pro_max_tenant_admin["headers"]
    guest = await _kiosk_cart(client, headers)
    cart = await client.get("/api/v1/guest/cart", headers=guest)
    assert cart.status_code == 200, cart.text
    assert len(cart.json()["items"]) == 1


async def test_kiosk_cash_checkout_requires_profile_first(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    guest = await _kiosk_cart(client, headers)
    resp = await client.post(
        "/api/v1/guest/send-kot", json={"payment_method": "cash"}, headers=guest
    )
    assert resp.status_code == 400, resp.text
    assert "name and phone" in resp.json()["detail"]


async def test_kiosk_cash_checkout_finalizes_bill_and_holds_kot_for_approval(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    guest = await _kiosk_cart(client, headers, price=90)
    await _set_guest_profile(client, guest)

    resp = await client.post(
        "/api/v1/guest/send-kot", json={"payment_method": "cash"}, headers=guest
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "paid_cash"
    assert body["bill_number"]
    order_id = body["order_id"]

    # The guest session is closed the instant the bill finalizes (same as any other
    # finalize) — a further cart/profile call now 404s as "session ended".
    cart = await client.get("/api/v1/guest/cart", headers=guest)
    assert cart.status_code == 404

    # Staff sees it as a pending-kitchen-approval row, not a real ticket yet.
    active = await client.get("/api/v1/kot/tickets/active", headers=headers)
    assert active.status_code == 200, active.text
    rows = [t for t in active.json() if t["order_id"] == order_id]
    assert len(rows) == 1
    assert rows[0]["is_pending_kitchen_approval"] is True
    assert rows[0]["bill_number"] == body["bill_number"]
    assert rows[0]["status"] == "pending"

    # A POS operator approves it with a plain "Send to Kitchen" — the bill is already
    # done, this just fires the ticket.
    sent = await client.post("/api/v1/kot", json={"order_id": order_id}, headers=headers)
    assert sent.status_code == 201, sent.text
    assert sent.json()["status"] == "new"

    # It's now a real ticket, still visible to the kitchen (order_billed_via_kot keeps
    # it from vanishing just because its order is already billed), no longer pending.
    active_after = await client.get("/api/v1/kot/tickets/active", headers=headers)
    rows_after = [t for t in active_after.json() if t["order_id"] == order_id]
    assert len(rows_after) == 1
    assert rows_after[0]["is_pending_kitchen_approval"] is False
    assert rows_after[0]["order_billed_via_kot"] is True
    assert rows_after[0]["bill_number"] == body["bill_number"]

    # Approving a second time has nothing left to send.
    sent_again = await client.post("/api/v1/kot", json={"order_id": order_id}, headers=headers)
    assert sent_again.status_code == 400
