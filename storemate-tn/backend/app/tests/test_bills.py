from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.tests.conftest import (
    auth_headers,
    create_category_and_tax_profile,
    create_pos_user,
    login,
)


async def _create_item(
    client: AsyncClient,
    headers: dict,
    *,
    selling_price_paise: int = 10_000,
    opening_stock: float = 50,
    barcode: str | None = None,
) -> str:
    category_id, tax_profile_id = await create_category_and_tax_profile(client, headers)
    resp = await client.post(
        "/api/v1/items",
        json={
            "category_id": category_id,
            "name_en": "Test Item",
            "name_ta": "பரிசோதனை பொருள்",
            "barcode": barcode,
            "unit": "pcs",
            "mrp_paise": selling_price_paise + 1_000,
            "selling_price_paise": selling_price_paise,
            "cost_price_paise": selling_price_paise - 2_000,
            "tax_profile_id": tax_profile_id,
            "opening_stock": opening_stock,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_create_bill_happy_path_decrements_stock(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers, selling_price_paise=10_000, opening_stock=50)

    resp = await client.post(
        "/api/v1/bills",
        json={
            "payment_mode": "cash",
            "items": [{"item_id": item_id, "qty": 2}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["subtotal_paise"] == 20_000
    assert body["total_paise"] == 23_600  # 18% GST from create_category_and_tax_profile
    assert body["bill_number"] == 1

    stock_resp = await client.get("/api/v1/stock", headers=headers)
    row = next(r for r in stock_resp.json()["items"] if r["item_id"] == item_id)
    assert row["quantity_on_hand"] == 48


async def test_insufficient_stock_blocks_sale(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers, opening_stock=1)

    resp = await client.post(
        "/api/v1/bills",
        json={"payment_mode": "cash", "items": [{"item_id": item_id, "qty": 5}]},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_hold_then_resume_round_trip(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers, opening_stock=50)

    hold_resp = await client.post(
        "/api/v1/bills",
        json={"payment_mode": "cash", "items": [{"item_id": item_id, "qty": 3}], "hold": True},
        headers=headers,
    )
    assert hold_resp.status_code == 201, hold_resp.text
    bill_id = hold_resp.json()["id"]
    assert hold_resp.json()["status"] == "held"

    # Holding must not touch stock — it isn't a completed sale yet.
    stock_resp = await client.get("/api/v1/stock", headers=headers)
    row = next(r for r in stock_resp.json()["items"] if r["item_id"] == item_id)
    assert row["quantity_on_hand"] == 50

    held_list = await client.get("/api/v1/bills", params={"status": "held"}, headers=headers)
    assert held_list.json()["total"] == 1

    resume_resp = await client.post(f"/api/v1/bills/{bill_id}/resume", headers=headers)
    assert resume_resp.status_code == 200, resume_resp.text
    resumed = resume_resp.json()
    assert resumed["items"][0]["item_id"] == item_id
    assert resumed["items"][0]["qty"] == 3

    # The held bill is popped — it no longer exists once resumed.
    get_resp = await client.get(f"/api/v1/bills/{bill_id}", headers=headers)
    assert get_resp.status_code == 404

    # Finalizing afresh gets a new bill number and now does decrement stock.
    finalize_resp = await client.post(
        "/api/v1/bills",
        json={"payment_mode": "cash", "items": resumed["items"]},
        headers=headers,
    )
    assert finalize_resp.status_code == 201
    assert finalize_resp.json()["status"] == "completed"

    stock_resp = await client.get("/api/v1/stock", headers=headers)
    row = next(r for r in stock_resp.json()["items"] if r["item_id"] == item_id)
    assert row["quantity_on_hand"] == 47


async def test_cancel_completed_bill_reverses_stock(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers, opening_stock=50)

    bill_resp = await client.post(
        "/api/v1/bills",
        json={"payment_mode": "cash", "items": [{"item_id": item_id, "qty": 4}]},
        headers=headers,
    )
    bill_id = bill_resp.json()["id"]

    cancel_resp = await client.post(f"/api/v1/bills/{bill_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["status"] == "cancelled"

    stock_resp = await client.get("/api/v1/stock", headers=headers)
    row = next(r for r in stock_resp.json()["items"] if r["item_id"] == item_id)
    assert row["quantity_on_hand"] == 50

    second_cancel = await client.post(f"/api/v1/bills/{bill_id}/cancel", headers=headers)
    assert second_cancel.status_code == 400


async def test_bill_number_sequential_per_store(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers, opening_stock=50)

    numbers = []
    for _ in range(3):
        resp = await client.post(
            "/api/v1/bills",
            json={"payment_mode": "cash", "items": [{"item_id": item_id, "qty": 1}]},
            headers=headers,
        )
        numbers.append(resp.json()["bill_number"])
    assert numbers == [1, 2, 3]


async def test_pos_user_only_sees_own_bills(
    client: AsyncClient, lite_tenant: dict, db_session: AsyncSession
) -> None:
    tenant = lite_tenant["tenant"]
    store = lite_tenant["store"]
    admin_tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    admin_headers = auth_headers(admin_tokens["access_token"])
    item_id = await _create_item(client, admin_headers, opening_stock=50)

    await create_pos_user(
        db_session,
        tenant_id=tenant.id,
        store_id=store.id,
        email="cashierA@tenanta.dev",
        password="Cashier@123",
    )
    cashier_tokens = await login(client, "cashierA@tenanta.dev", "Cashier@123")
    cashier_headers = auth_headers(cashier_tokens["access_token"])

    admin_bill = await client.post(
        "/api/v1/bills",
        json={"payment_mode": "cash", "items": [{"item_id": item_id, "qty": 1}]},
        headers=admin_headers,
    )
    cashier_bill = await client.post(
        "/api/v1/bills",
        json={"payment_mode": "cash", "items": [{"item_id": item_id, "qty": 1}]},
        headers=cashier_headers,
    )

    cashier_search = await client.get("/api/v1/bills", headers=cashier_headers)
    ids = [b["id"] for b in cashier_search.json()["items"]]
    assert cashier_bill.json()["id"] in ids
    assert admin_bill.json()["id"] not in ids

    # A cashier can't fetch an admin's bill directly either (404, not 403).
    get_admin_bill = await client.get(
        f"/api/v1/bills/{admin_bill.json()['id']}", headers=cashier_headers
    )
    assert get_admin_bill.status_code == 404


async def test_saved_bill_search_window_flags_clamped_request(
    client: AsyncClient, lite_tenant: dict, db_session: AsyncSession
) -> None:
    from app.models.bill import Bill

    tenant = lite_tenant["tenant"]
    store = lite_tenant["store"]
    admin = lite_tenant["admin"]

    old_bill = Bill(
        tenant_id=tenant.id,
        store_id=store.id,
        bill_number=1,
        cashier_id=admin.id,
        subtotal_paise=1000,
        total_paise=1000,
        payment_mode="cash",
    )
    db_session.add(old_bill)
    await db_session.flush()
    # Backdate it beyond the Lite plan's 7-day window (set directly since
    # created_at has a server_default that fires at INSERT time).
    old_bill.created_at = datetime.now(UTC) - timedelta(days=30)
    await db_session.flush()

    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    unbounded = await client.get("/api/v1/bills", headers=headers)
    assert unbounded.status_code == 200
    body = unbounded.json()
    assert body["saved_bill_days"] == 7
    assert body["window_start"] is not None
    assert body["requested_from_clamped"] is False  # nothing explicit was asked for and cut
    assert all(b["id"] != str(old_bill.id) for b in body["items"])  # silently outside window

    far_back = (datetime.now(UTC) - timedelta(days=60)).date().isoformat()
    clamped = await client.get("/api/v1/bills", params={"date_from": far_back}, headers=headers)
    assert clamped.json()["requested_from_clamped"] is True


async def test_tax_profile_with_igst_pct_still_bills_using_cgst_sgst(
    client: AsyncClient, lite_tenant: dict
) -> None:
    """A tax profile can carry an igst_pct (the equivalent inter-state rate
    stored alongside cgst/sgst on the same profile, per
    docs/DATABASE_SCHEMA.md) without blocking an ordinary intra-state sale —
    only cgst_pct/sgst_pct are ever charged in Phase 5."""
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    category_id, _ = await create_category_and_tax_profile(client, headers)

    profile_resp = await client.post(
        "/api/v1/settings/tax-profiles",
        json={"name": "GST 18% (with IGST ref)", "cgst_pct": 9, "sgst_pct": 9, "igst_pct": 18},
        headers=headers,
    )
    item_resp = await client.post(
        "/api/v1/items",
        json={
            "category_id": category_id,
            "name_en": "Dual-rate item",
            "name_ta": "பொருள்",
            "unit": "pcs",
            "mrp_paise": 1000,
            "selling_price_paise": 1000,
            "cost_price_paise": 800,
            "tax_profile_id": profile_resp.json()["id"],
            "opening_stock": 10,
        },
        headers=headers,
    )
    item_id = item_resp.json()["id"]

    resp = await client.post(
        "/api/v1/bills",
        json={"payment_mode": "cash", "items": [{"item_id": item_id, "qty": 1}]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["cgst_paise"] == 90
    assert body["sgst_paise"] == 90
    # 1000 + 90 + 90 = 1180 paise (₹11.80), rounded to the nearest rupee -> ₹12.00.
    assert body["total_paise"] == 1200


async def test_print_payload_includes_company_and_line_items(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers, opening_stock=10)

    bill_resp = await client.post(
        "/api/v1/bills",
        json={"payment_mode": "upi", "items": [{"item_id": item_id, "qty": 1}]},
        headers=headers,
    )
    bill_id = bill_resp.json()["id"]

    print_resp = await client.post(f"/api/v1/bills/{bill_id}/print", headers=headers)
    assert print_resp.status_code == 200, print_resp.text
    payload = print_resp.json()
    assert payload["bill_number"] == bill_resp.json()["bill_number"]
    assert payload["company"]["legal_name"]
    assert len(payload["items"]) == 1
    assert payload["total_paise"] == bill_resp.json()["total_paise"]

    bill_check = await client.get(f"/api/v1/bills/{bill_id}", headers=headers)
    assert bill_check.json()["printed_count"] == 1
