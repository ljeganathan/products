"""Phase 25 — QR self-order: one QR per table (not per seat), a shared cart everyone
scanning that table's code orders into, and its interaction with staff-side
billing/user-listing.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import async_session_maker
from tests.conftest import _set_platform_admin

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _default_location_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/api/v1/locations", headers=headers)
    return resp.json()[0]["id"]


async def _section_id(client: AsyncClient, headers: dict, name_en: str) -> str:
    resp = await client.get("/api/v1/sections", headers=headers)
    return next(s["id"] for s in resp.json() if s["name_en"] == name_en)


async def _create_table(
    client: AsyncClient, headers: dict, location_id: str, section_id: str, **overrides
) -> dict:
    payload = {
        "location_id": location_id,
        "section_id": section_id,
        "table_number": "QR1",
        "seating_capacity": 2,
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/tables", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


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


async def _generate_qr(client: AsyncClient, headers: dict, table_id: str) -> str:
    resp = await client.post(f"/api/v1/tables/{table_id}/qr-code", headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["qr_token"]


async def _start_guest_session(client: AsyncClient, qr_token: str) -> dict:
    resp = await client.post(f"/api/v1/guest/sessions/{qr_token}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _guest_headers(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['guest_token']}"}


async def test_qr_generation_gated_pro_max_only_and_one_per_table(
    client: AsyncClient, tenant_admin: dict, pro_max_tenant_admin: dict
):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)

    lite_resp = await client.post(f"/api/v1/tables/{table['id']}/qr-code", headers=headers)
    assert lite_resp.status_code == 403

    pm_headers = pro_max_tenant_admin["headers"]
    pm_location_id = await _default_location_id(client, pm_headers)
    pm_section_id = await _section_id(client, pm_headers, "AC")
    pm_table = await _create_table(client, pm_headers, pm_location_id, pm_section_id)

    resp = await client.post(f"/api/v1/tables/{pm_table['id']}/qr-code", headers=pm_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["table_number"] == pm_table["table_number"]
    assert body["qr_token"]

    # Idempotent — calling again returns the exact same code, never a second one.
    again = await client.post(f"/api/v1/tables/{pm_table['id']}/qr-code", headers=pm_headers)
    assert again.status_code == 201
    assert again.json()["qr_token"] == body["qr_token"]

    fetched = await client.get(f"/api/v1/tables/{pm_table['id']}/qr-code", headers=pm_headers)
    assert fetched.status_code == 200
    assert fetched.json()["qr_token"] == body["qr_token"]


async def test_guest_session_requires_toggle_and_never_needs_a_location_pick(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    qr_token = await _generate_qr(client, headers, table["id"])

    # Toggle is off by default even on Pro Max.
    off_resp = await client.post(f"/api/v1/guest/sessions/{qr_token}")
    assert off_resp.status_code == 403

    await _enable_qr_self_order(client, headers)

    session = await _start_guest_session(client, qr_token)
    assert session["location_id"] == location_id
    assert session["table_number"] == table["table_number"]
    assert session["order_id"] is None
    assert session["guest_token"]
    assert "customer_number" not in session
    assert "party_label" not in session

    bad_resp = await client.post("/api/v1/guest/sessions/does-not-exist")
    assert bad_resp.status_code == 404


async def test_multiple_scans_of_same_table_qr_share_one_cart(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """The actual production requirement: no per-seat QR to maintain — anyone scanning
    a table's one code orders into the same shared cart, auto-detected purely by which
    table's QR was scanned.
    """
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_qr(client, headers, table["id"])

    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=150)

    phone_a = _guest_headers(await _start_guest_session(client, qr_token))
    await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=phone_a
    )

    # A second phone scanning the exact same QR joins the same order.
    phone_b_session = await _start_guest_session(client, qr_token)
    assert phone_b_session["order_id"] is not None
    phone_b = _guest_headers(phone_b_session)

    cart_from_b = await client.get("/api/v1/guest/cart", headers=phone_b)
    assert cart_from_b.status_code == 200
    assert cart_from_b.json()["id"] == phone_b_session["order_id"]
    assert len(cart_from_b.json()["items"]) == 1

    # Rescanning later (e.g. phone A comes back) still resolves to the same order.
    rescan = await _start_guest_session(client, qr_token)
    assert rescan["order_id"] == phone_b_session["order_id"]


async def test_guest_full_order_to_bill_flow(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_qr(client, headers, table["id"])

    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], name_en="Filter Coffee", price=30)

    guest = _guest_headers(await _start_guest_session(client, qr_token))

    menu = await client.get("/api/v1/guest/menu", headers=guest)
    assert menu.status_code == 200
    assert any(i["id"] == item["id"] for i in menu.json())

    cart = await client.post(
        "/api/v1/guest/cart",
        json={"items": [{"item_id": item["id"], "quantity": 2}]},
        headers=guest,
    )
    assert cart.status_code == 200, cart.text
    order = cart.json()
    assert order["source"] == "guest"
    assert order["party_label"] is None
    assert order["waiter_id"] is None

    kot = await client.post("/api/v1/guest/send-kot", headers=guest)
    assert kot.status_code == 201, kot.text

    status_resp = await client.get("/api/v1/guest/order-status", headers=guest)
    assert status_resp.status_code == 200
    tickets = status_resp.json()
    assert len(tickets) == 1
    assert tickets[0]["source"] == "guest"
    assert tickets[0]["order_id"] == order["id"]

    # Staff sees exactly the same ticket via the ordinary KOT Tickets endpoint.
    staff_tickets = await client.get("/api/v1/kot/tickets/active", headers=headers)
    assert any(t["order_id"] == order["id"] and t["source"] == "guest" for t in staff_tickets.json())

    preview = await client.get("/api/v1/guest/bill-preview", headers=guest)
    assert preview.status_code == 200, preview.text
    assert preview.json()["grand_total"] > 0

    claim = await client.post("/api/v1/guest/request-bill", headers=guest)
    assert claim.status_code == 200
    assert claim.json()["status"] == "payment_claimed"

    # Guest can never finalize a real bill — no valid staff token type at all.
    guest_bill_attempt = await client.post(
        "/api/v1/bills", json={"order_id": order["id"], "payments": []}, headers=guest
    )
    assert guest_bill_attempt.status_code == 401

    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 60.0}]},
        headers=headers,
    )
    assert bill.status_code == 201, bill.text

    # Ordering session is closed once staff finalizes — the table's QR is a clean
    # slate again (rescanning starts a brand-new order, not the just-billed one).
    fresh_scan = await _start_guest_session(client, qr_token)
    assert fresh_scan["order_id"] is None


async def test_rescan_after_session_expiry_creates_fresh_session(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Regression: a guest_sessions row that ticked past its `expires_at` but is still
    flagged `status='active'` (nothing ever sweeps expiry) must be closed before a
    rescan inserts the table's next session — otherwise the insert trips the partial
    unique index `uq_guest_sessions_active_table` (at most one active row per table)
    with a raw 500, which the guest frontend showed as "This QR code isn't valid, or
    ordering isn't available" days after a table's first-ever guest session expired.
    """
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_qr(client, headers, table["id"])

    first = await _start_guest_session(client, qr_token)

    async with async_session_maker() as session:
        await _set_platform_admin(session)
        await session.execute(
            text(
                "UPDATE guest_sessions SET expires_at = now() - interval '1 hour' "
                "WHERE table_id = :table_id"
            ),
            {"table_id": table["id"]},
        )
        await session.commit()

    rescan = await _start_guest_session(client, qr_token)
    assert rescan["order_id"] is None
    assert rescan["guest_token"] != first["guest_token"]


async def test_stale_payment_claimed_session_does_not_break_next_scan(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Regression: `create_or_resume_session`'s "is there already a session for this
    table" check used to look only at `status == 'active'`, ignoring `payment_claimed`
    sessions entirely. So once a guest requested the bill (status -> payment_claimed)
    and that row sat unfinalized past its expiry, the next scan created a *second*,
    independent 'active' row for the same table instead of resuming/replacing the
    payment_claimed one — leaving two "current" rows, which crashed every subsequent
    guest action (add item, save name) with a raw 500
    (`sqlalchemy.exc.MultipleResultsFound`) once `_get_active_session_or_404` tried to
    fetch exactly one. Both symptoms a real customer saw: "Couldn't add that item" and
    "Couldn't save" on the guest app.
    """
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_qr(client, headers, table["id"])
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=90)

    guest = _guest_headers(await _start_guest_session(client, qr_token))
    await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )
    claim = await client.post("/api/v1/guest/request-bill", headers=guest)
    assert claim.status_code == 200
    assert claim.json()["status"] == "payment_claimed"

    # Force that payment_claimed session into the past without ever finalizing it —
    # the exact stuck state a network blip or an abandoned bill-request leaves behind.
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        await session.execute(
            text(
                "UPDATE guest_sessions SET expires_at = now() - interval '1 hour' "
                "WHERE table_id = :table_id"
            ),
            {"table_id": table["id"]},
        )
        await session.commit()

    rescan = await _start_guest_session(client, qr_token)
    assert rescan["order_id"] is None
    new_guest = _guest_headers(rescan)

    add_item = await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=new_guest
    )
    assert add_item.status_code == 200, add_item.text

    save_profile = await client.patch(
        "/api/v1/guest/sessions/me", json={"customer_name": "sen"}, headers=new_guest
    )
    assert save_profile.status_code == 200, save_profile.text


async def test_kot_tickets_list_shows_guest_payment_claimed(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Once a guest taps Request Bill on their phone, staff picking up that ticket from
    the KOT Tickets list (to bill/print it) must be able to see it was already claimed
    as paid — the live payment_claimed websocket toast is easy to miss, this flag is
    the persistent fallback.
    """
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_qr(client, headers, table["id"])
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=90)

    guest = _guest_headers(await _start_guest_session(client, qr_token))
    await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )
    await client.post("/api/v1/guest/send-kot", headers=guest)

    before = await client.get("/api/v1/kot/tickets/active", headers=headers)
    assert before.json()[0]["guest_payment_claimed"] is False

    claim = await client.post("/api/v1/guest/request-bill", headers=guest)
    assert claim.status_code == 200

    after = await client.get("/api/v1/kot/tickets/active", headers=headers)
    assert after.json()[0]["guest_payment_claimed"] is True


async def test_system_account_excluded_from_user_listing_and_seat_cap(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_qr(client, headers, table["id"])
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"])
    guest = _guest_headers(await _start_guest_session(client, qr_token))

    users_before = (await client.get("/api/v1/users", headers=headers)).json()

    await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )

    users_after = (await client.get("/api/v1/users", headers=headers)).json()
    assert len(users_after) == len(users_before)
    assert not any("QRORDER" in u["user_id"] for u in users_after)
