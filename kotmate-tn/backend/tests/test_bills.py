import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db.session import async_session_maker
from app.models import AuditLog, HotelMaster

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


async def _create_tax_rule(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {"name": "Standard GST", "cgst_rate": 11.9, "sgst_rate": 11.9, "is_default": True}
    payload.update(overrides)
    resp = await client.post("/api/v1/tax-rules", json=payload, headers=headers)
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


async def _order_with_200_subtotal(
    client: AsyncClient, headers: dict, location_id: str, section_id: str
) -> dict:
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=200)
    return await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )


async def test_finalize_bill_computes_tax_and_round_off(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    await _create_tax_rule(client, headers)
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)

    resp = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 248.0}]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["subtotal"] == 200
    # CGST/SGST always two distinct fields/lines, never merged, even when equal.
    assert body["cgst_amount"] == 23.8
    assert body["sgst_amount"] == 23.8
    # CLAUDE.md §9 worked example shape: 247.60 -> 248.00, round_off = +0.40.
    assert body["round_off_amount"] == 0.4
    assert body["grand_total"] == 248.0
    assert body["status"] == "finalized"
    assert body["bill_number"]

    order_after = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert order_after["status"] == "billed"


async def test_repeat_kot_add_on_consolidates_into_one_bill_line(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Production feedback: ordering more of an item that's already been sent to KOT
    correctly becomes a second, separate `order_items`/`kot_ticket_items` row (see
    test_kot.py's own regression test for that) — but a customer's bill, its on-screen
    preview, and the physical print must still show that as one line with the combined
    quantity, not two entries for the same item. KOT tickets themselves stay separate.
    """
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    await _create_tax_rule(client, headers)
    category = await _create_category(client, headers)
    dosai = await _create_item(client, headers, category["id"], name_en="Dosai", price=50)

    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": dosai["id"], "quantity": 1}]
    )
    sent_line_id = order["items"][0]["id"]
    first_kot = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert first_kot.status_code == 201, first_kot.text

    updated = await client.patch(
        f"/api/v1/orders/{order['id']}",
        json={
            "items": [
                {"id": sent_line_id, "item_id": dosai["id"], "quantity": 1},
                {"item_id": dosai["id"], "quantity": 1},
            ]
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert len(updated.json()["items"]) == 2  # still two order_items rows

    second_kot = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert second_kot.status_code == 201, second_kot.text

    preview = await client.post(
        "/api/v1/bills/preview", json={"order_id": order["id"]}, headers=headers
    )
    assert preview.status_code == 200, preview.text
    assert len(preview.json()["items"]) == 1
    assert preview.json()["items"][0]["quantity"] == 2
    assert preview.json()["items"][0]["line_total"] == 100.0

    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 124.0}]},
        headers=headers,
    )
    assert bill.status_code == 201, bill.text
    body = bill.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 2
    assert body["items"][0]["line_total"] == 100.0

    fetched = await client.get(f"/api/v1/bills/{body['id']}", headers=headers)
    assert len(fetched.json()["items"]) == 1
    assert fetched.json()["items"][0]["quantity"] == 2


async def test_billed_order_drops_from_kot_tickets_popup(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)
    await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)

    tickets_before = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    assert any(t["order_id"] == order["id"] for t in tickets_before)

    await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "upi", "amount": 200.0}]},
        headers=headers,
    )

    tickets_after = (await client.get("/api/v1/kot/tickets/active", headers=headers)).json()
    assert not any(t["order_id"] == order["id"] for t in tickets_after)


async def test_split_payment_must_equal_grand_total(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)

    resp = await client.post(
        "/api/v1/bills",
        json={
            "order_id": order["id"],
            "payments": [{"method": "cash", "amount": 100.0}, {"method": "upi", "amount": 50.0}],
        },
        headers=headers,
    )
    assert resp.status_code == 400

    ok_resp = await client.post(
        "/api/v1/bills",
        json={
            "order_id": order["id"],
            "payments": [{"method": "cash", "amount": 100.0}, {"method": "upi", "amount": 100.0}],
        },
        headers=headers,
    )
    assert ok_resp.status_code == 201
    assert len(ok_resp.json()["payments"]) == 2


async def test_waiter_cannot_finalize_bill(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)
    waiter_headers = await _waiter_headers(client, headers)

    resp = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 200.0}]},
        headers=waiter_headers,
    )
    assert resp.status_code == 403

    # Also blocked from reading bill history/search — waiter has no reports access (§5).
    assert (await client.get("/api/v1/bills", headers=waiter_headers)).status_code == 403


async def _create_discount_rule(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {"name": "Test Rule", "type": "flat_percent", "discount_mode": "percent", "value": 10}
    payload.update(overrides)
    resp = await client.post("/api/v1/discount-rules", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_flat_percent_discount_auto_applies(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)
    await _create_discount_rule(client, headers, name="Festival Offer", type="flat_percent", value=10)

    preview = await client.post(
        "/api/v1/bills/preview", json={"order_id": order["id"]}, headers=headers
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["subtotal"] == 200
    assert body["discount_amount"] == 20.0
    assert body["discount_note"] == "Festival Offer: -₹20.00"
    # No tax rule registered for this tenant -> zero tax, so grand_total == net taxable.
    assert body["grand_total"] == 180.0


async def test_item_level_discount_blocked_on_lite_allowed_on_pro_max(
    client: AsyncClient, tenant_admin: dict, pro_max_tenant_admin: dict
):
    lite_headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, lite_headers)
    section_id = await _section_id(client, lite_headers, "AC")
    order = await _order_with_200_subtotal(client, lite_headers, location_id, section_id)
    item_id = order["items"][0]["item_id"]
    # Rule creation itself isn't plan-gated (only application at billing time is) — a
    # Lite tenant can create an item_level rule, it just never auto-applies.
    await _create_discount_rule(
        client, lite_headers, name="Item Offer", type="item_level", discount_mode="rupee", value=15,
        item_id=item_id,
    )

    blocked = await client.post(
        "/api/v1/bills/preview", json={"order_id": order["id"]}, headers=lite_headers
    )
    assert blocked.status_code == 200
    assert blocked.json()["discount_amount"] == 0.0

    pm_headers = pro_max_tenant_admin["headers"]
    pm_location_id = await _default_location_id(client, pm_headers)
    pm_section_id = await _section_id(client, pm_headers, "AC")
    pm_order = await _order_with_200_subtotal(client, pm_headers, pm_location_id, pm_section_id)
    pm_item_id = pm_order["items"][0]["item_id"]
    await _create_discount_rule(
        client, pm_headers, name="Item Offer", type="item_level", discount_mode="rupee", value=15,
        item_id=pm_item_id,
    )

    allowed = await client.post(
        "/api/v1/bills/preview", json={"order_id": pm_order["id"]}, headers=pm_headers
    )
    assert allowed.status_code == 200
    assert allowed.json()["discount_amount"] == 15.0


async def test_item_level_discount_capped_at_line_total(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)
    item_id = order["items"][0]["item_id"]
    await _create_discount_rule(
        client, headers, name="Huge Offer", type="item_level", discount_mode="rupee", value=9999,
        item_id=item_id,
    )

    resp = await client.post(
        "/api/v1/bills/preview", json={"order_id": order["id"]}, headers=headers
    )
    assert resp.status_code == 200
    # Rule value 9999 off a 200-rupee line — capped to the line's own total.
    assert resp.json()["discount_amount"] == 200.0


async def test_coupon_discount_applies_rule_percent(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)

    await _create_discount_rule(
        client, headers, name="Save10", type="coupon", value=10, coupon_code="SAVE10"
    )

    resp = await client.post(
        "/api/v1/bills/preview",
        json={"order_id": order["id"], "coupon_code": "SAVE10"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["discount_amount"] == 20.0

    bad_coupon = await client.post(
        "/api/v1/bills/preview",
        json={"order_id": order["id"], "coupon_code": "NOPE"},
        headers=headers,
    )
    assert bad_coupon.status_code == 400


async def test_expired_flat_rule_does_not_apply(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)
    await _create_discount_rule(
        client, headers, name="Expired Offer", type="flat_percent", value=10, expires_at="2020-01-01"
    )

    resp = await client.post(
        "/api/v1/bills/preview", json={"order_id": order["id"]}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["discount_amount"] == 0.0


async def test_deactivated_flat_rule_does_not_apply(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)
    rule = await _create_discount_rule(client, headers, name="Toggled Off", type="flat_percent", value=10)
    await client.patch(
        f"/api/v1/discount-rules/{rule['id']}", json={"is_active": False}, headers=headers
    )

    resp = await client.post(
        "/api/v1/bills/preview", json={"order_id": order["id"]}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["discount_amount"] == 0.0


async def test_multiple_active_flat_rules_best_for_customer_wins(
    client: AsyncClient, tenant_admin: dict
):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)
    await _create_discount_rule(client, headers, name="Small Offer", type="flat_percent", value=5)
    await _create_discount_rule(client, headers, name="Big Offer", type="flat_percent", value=20)

    resp = await client.post(
        "/api/v1/bills/preview", json={"order_id": order["id"]}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["discount_amount"] == 40.0
    assert body["discount_note"] == "Big Offer: -₹40.00"


async def test_item_flat_and_coupon_discounts_stack(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)
    item_id = order["items"][0]["item_id"]

    await _create_discount_rule(
        client, headers, name="Item Offer", type="item_level", discount_mode="rupee", value=20,
        item_id=item_id,
    )
    await _create_discount_rule(client, headers, name="Flat Offer", type="flat_percent", value=10)
    await _create_discount_rule(
        client, headers, name="Coupon Offer", type="coupon", value=10, coupon_code="STACK10"
    )

    resp = await client.post(
        "/api/v1/bills/preview",
        json={"order_id": order["id"], "coupon_code": "STACK10"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    # item: 20 off 200 -> 180 remaining. flat 10% of 180 = 18 -> 162 remaining.
    # coupon 10% of 162 = 16.2.
    assert body["discount_amount"] == 20 + 18 + 16.2
    assert "Item Offer" in body["discount_note"]
    assert "Flat Offer" in body["discount_note"]
    assert "Coupon Offer" in body["discount_note"]


async def test_old_bill_search_and_reprint_produces_identical_bill(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)

    finalized = (
        await client.post(
            "/api/v1/bills",
            json={"order_id": order["id"], "payments": [{"method": "upi", "amount": 200.0}]},
            headers=headers,
        )
    ).json()

    search = await client.get(
        "/api/v1/bills", params={"bill_number": finalized["bill_number"]}, headers=headers
    )
    assert search.status_code == 200
    assert any(b["id"] == finalized["id"] for b in search.json())

    reprint = await client.post(f"/api/v1/bills/{finalized['id']}/reprint", headers=headers)
    assert reprint.status_code == 200
    reprinted = reprint.json()
    for key in (
        "bill_number",
        "subtotal",
        "cgst_amount",
        "sgst_amount",
        "grand_total",
        "items",
        "payments",
        "party_label",
    ):
        assert reprinted[key] == finalized[key]


async def test_skip_print_finalizes_without_printing_then_reprint_dispatches(
    client: AsyncClient, tenant_admin: dict
):
    """Phase 21 print-preview flow: finalizing with skip_print=True still creates the
    bill (one bill_number, one Bill row) but withholds the print dispatch until an
    explicit reprint call — proving "finalize silently, then reprint" is safe to reuse
    as the preview-then-print mechanism rather than inventing a second print path.
    """
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Counter Bill Printer",
            "target": "bill",
            "printer_type": "thermal",
            # usb rather than network — this test exercises the skip_print/reprint
            # dispatch flow itself, not real network reachability (network/wifi
            # transport is covered live against real hardware, not in this suite).
            "connection_type": "usb",
        },
        headers=headers,
    )
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)

    finalized = (
        await client.post(
            "/api/v1/bills",
            json={
                "order_id": order["id"],
                "payments": [{"method": "cash", "amount": 200.0}],
                "skip_print": True,
            },
            headers=headers,
        )
    ).json()
    assert finalized["printed"] is False

    reprint = (await client.post(f"/api/v1/bills/{finalized['id']}/reprint", headers=headers)).json()
    assert reprint["printed"] is True
    assert reprint["id"] == finalized["id"]
    assert reprint["bill_number"] == finalized["bill_number"]

    # Exactly one bill was created — skip_print never triggers a second finalize.
    search = await client.get(
        "/api/v1/bills", params={"bill_number": finalized["bill_number"]}, headers=headers
    )
    assert len(search.json()) == 1


async def test_bill_search_filters_by_section_and_cashier(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    ac_section_id = await _section_id(client, headers, "AC")
    non_ac_section_id = await _section_id(client, headers, "Non-AC")

    ac_order = await _order_with_200_subtotal(client, headers, location_id, ac_section_id)
    ac_bill = (
        await client.post(
            "/api/v1/bills",
            json={"order_id": ac_order["id"], "payments": [{"method": "upi", "amount": 200.0}]},
            headers=headers,
        )
    ).json()
    non_ac_order = await _order_with_200_subtotal(client, headers, location_id, non_ac_section_id)
    non_ac_bill = (
        await client.post(
            "/api/v1/bills",
            json={"order_id": non_ac_order["id"], "payments": [{"method": "upi", "amount": 200.0}]},
            headers=headers,
        )
    ).json()

    section_search = await client.get(
        "/api/v1/bills", params={"section_id": ac_section_id}, headers=headers
    )
    assert section_search.status_code == 200
    section_ids = [b["id"] for b in section_search.json()]
    assert ac_bill["id"] in section_ids
    assert non_ac_bill["id"] not in section_ids

    cashier_id = ac_bill["pos_user_id"]
    cashier_search = await client.get(
        "/api/v1/bills", params={"pos_user_id": cashier_id}, headers=headers
    )
    assert cashier_search.status_code == 200
    assert all(b["pos_user_id"] == cashier_id for b in cashier_search.json())
    assert ac_bill["id"] in [b["id"] for b in cashier_search.json()]


async def test_audit_log_written_for_large_discount(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    tenant_id = pro_max_tenant_admin["tenant"]["id"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=1000)
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )
    await _create_discount_rule(client, headers, name="Huge Offer", type="flat_percent", value=90)

    resp = await client.post(
        "/api/v1/bills",
        json={
            "order_id": order["id"],
            "payments": [{"method": "cash", "amount": 100.0}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["discount_amount"] == 900.0

    async with async_session_maker() as session:
        await session.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))
        rows = (
            await session.execute(select(AuditLog).where(AuditLog.tenant_id == uuid.UUID(tenant_id)))
        ).scalars().all()
    assert any(r.action == "discount_applied" for r in rows)


async def test_bill_printer_dispatches_with_qr_when_upi_configured(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    tenant_id = pro_max_tenant_admin["tenant"]["id"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)

    no_printer = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 200.0}]},
        headers=headers,
    )
    assert no_printer.json()["printed"] is False

    await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Counter Bill Printer",
            "target": "bill",
            "printer_type": "thermal",
            # usb rather than network — this test exercises the QR/dispatch logic
            # itself, not real network reachability.
            "connection_type": "usb",
        },
        headers=headers,
    )
    async with async_session_maker() as session:
        await session.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))
        session.add(
            HotelMaster(
                tenant_id=uuid.UUID(tenant_id),
                location_id=uuid.UUID(location_id),
                name="Test Hotel",
                upi_id="hotel@upi",
                show_tamil_names=True,
            )
        )
        await session.commit()

    order2 = await _order_with_200_subtotal(client, headers, location_id, section_id)
    with_printer = await client.post(
        "/api/v1/bills",
        json={"order_id": order2["id"], "payments": [{"method": "cash", "amount": 200.0}]},
        headers=headers,
    )
    assert with_printer.status_code == 201
    assert with_printer.json()["printed"] is True


async def test_unreachable_network_printer_reports_printed_false_with_error(
    client: AsyncClient, tenant_admin: dict
):
    """Regression test for a real bug: a network/wifi printer used to be marked
    `printed: true` unconditionally, even though nothing was ever sent to it (the
    dispatcher only rendered and logged the bytes — see printing/dispatcher.py's
    history). It must now actually attempt delivery and report failure honestly when
    the printer is unreachable, with a cashier-safe `print_error` message.
    """
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Unreachable WiFi Printer",
            "target": "bill",
            "printer_type": "thermal",
            "connection_type": "network",
            "connection_details": {"ip_address": "10.255.255.1", "port": "9100"},
        },
        headers=headers,
    )
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)

    resp = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 200.0}]},
        headers=headers,
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["printed"] is False
    assert body["print_job"] is None
    assert body["print_error"] is not None


async def test_double_billing_same_order_rejected(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    order = await _order_with_200_subtotal(client, headers, location_id, section_id)

    first = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 200.0}]},
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 200.0}]},
        headers=headers,
    )
    assert second.status_code == 400
