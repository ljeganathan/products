from datetime import date

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

TODAY = date.today().isoformat()


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
    payload = {"name_en": "Meals", "category_id": category_id, "price": 200}
    payload.update(overrides)
    resp = await client.post("/api/v1/items", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_tax_rule(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {"name": "Standard GST", "cgst_rate": 2.5, "sgst_rate": 2.5, "is_default": True}
    payload.update(overrides)
    resp = await client.post("/api/v1/tax-rules", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_waiter(client: AsyncClient, headers: dict, location_id: str, **overrides) -> dict:
    payload = {"location_id": location_id, "waiter_number": "W1", "name": "Ravi", "incentive_rate": 2}
    payload.update(overrides)
    resp = await client.post("/api/v1/waiters", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_cashier(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {
        "local_handle": "cashier01",
        "name": "Cashier One",
        "role": "pos_user",
        "password": "password123",
        "incentive_rate": 1,
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/users", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    user = resp.json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": user["user_id"], "password": "password123"}
    )
    return {"user": user, "headers": {"Authorization": f"Bearer {login.json()['access_token']}"}}


async def _bill_one_order(
    client: AsyncClient,
    cashier_headers: dict,
    location_id: str,
    section_id: str,
    item_id: str,
    waiter_id: str,
) -> dict:
    """Creates + bills a 2-quantity order (subtotal 400 at price=200) as the cashier,
    with the given waiter attributed — so `pos_user_id` = cashier, `waiter_id` = waiter,
    covering the "both incentive reports populated, no double count" scenario.
    """
    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "waiter_id": waiter_id,
                "items": [{"item_id": item_id, "quantity": 2}],
            },
            headers=cashier_headers,
        )
    ).json()
    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 420.0}]},
        headers=cashier_headers,
    )
    assert bill.status_code == 201, bill.text
    return bill.json()


async def _setup_one_bill(client: AsyncClient, tenant_admin: dict) -> dict:
    """Full scenario used by most reconciliation tests: one ₹200 x 2 = ₹400 bill, 2.5%
    CGST + 2.5% SGST (₹10 each, ₹420 grand total, round_off 0), waiter incentive_rate=2%
    (₹8), cashier incentive_rate=1% (₹4).
    """
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    await _create_tax_rule(client, headers)
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"])
    waiter = await _create_waiter(client, headers, location_id)
    cashier = await _create_cashier(client, headers)

    bill = await _bill_one_order(
        client, cashier["headers"], location_id, section_id, item["id"], waiter["id"]
    )
    return {
        "bill": bill,
        "item": item,
        "category": category,
        "waiter": waiter,
        "cashier": cashier,
        "location_id": location_id,
    }


async def test_sales_summary_reconciles_with_bill(client: AsyncClient, tenant_admin: dict):
    ctx = await _setup_one_bill(client, tenant_admin)
    headers = tenant_admin["headers"]

    resp = await client.get(
        "/api/v1/reports/sales-summary", params={"date_from": TODAY, "date_to": TODAY}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    bill = ctx["bill"]
    assert body["bill_count"] == 1
    assert body["subtotal"] == bill["subtotal"] == 400.0
    assert body["cgst_amount"] == bill["cgst_amount"] == 10.0
    assert body["sgst_amount"] == bill["sgst_amount"] == 10.0
    assert body["grand_total"] == bill["grand_total"] == 420.0
    assert body["average_bill_value"] == 420.0


async def test_item_and_category_wise_reconcile(client: AsyncClient, tenant_admin: dict):
    ctx = await _setup_one_bill(client, tenant_admin)
    headers = tenant_admin["headers"]

    item_resp = await client.get(
        "/api/v1/reports/item-wise", params={"date_from": TODAY, "date_to": TODAY}, headers=headers
    )
    assert item_resp.status_code == 200
    item_body = item_resp.json()
    assert item_body["total_revenue"] == 400.0
    row = next(r for r in item_body["rows"] if r["item_id"] == ctx["item"]["id"])
    assert row["quantity_sold"] == 2
    assert row["revenue"] == 400.0

    cat_resp = await client.get(
        "/api/v1/reports/category-wise", params={"date_from": TODAY, "date_to": TODAY}, headers=headers
    )
    assert cat_resp.status_code == 200
    cat_body = cat_resp.json()
    assert cat_body["total_revenue"] == 400.0
    cat_row = next(r for r in cat_body["rows"] if r["category_id"] == ctx["category"]["id"])
    assert cat_row["revenue"] == 400.0


async def test_item_wise_grouped_by_category_ordered_by_revenue_desc(
    client: AsyncClient, tenant_admin: dict
):
    """Production feedback round 4: item-wise groups by category — categories ordered by
    their own total revenue descending, items within a category ordered by their own
    revenue descending. Mains (200) outranks Beverages (30 + 20 = 50)... wait, Mains'
    single item (200) still outranks Beverages' combined total (50), and within
    Beverages, Coffee (30) outranks Tea (20).
    """
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    await _create_tax_rule(client, headers)

    mains = await _create_category(client, headers, "Mains")
    beverages = await _create_category(client, headers, "Beverages")
    meals = await _create_item(client, headers, mains["id"], name_en="Meals", price=200)
    coffee = await _create_item(client, headers, beverages["id"], name_en="Coffee", price=30)
    tea = await _create_item(client, headers, beverages["id"], name_en="Tea", price=20)

    async def _bill_single_item(item_id: str, amount: float) -> None:
        order = (
            await client.post(
                "/api/v1/orders",
                json={
                    "location_id": location_id,
                    "section_id": section_id,
                    "items": [{"item_id": item_id, "quantity": 1}],
                },
                headers=headers,
            )
        ).json()
        resp = await client.post(
            "/api/v1/bills",
            json={"order_id": order["id"], "payments": [{"method": "cash", "amount": amount}]},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

    # 2.5% CGST + 2.5% SGST each, round-half-up to the nearest rupee.
    await _bill_single_item(meals["id"], 210.0)
    await _bill_single_item(coffee["id"], 32.0)
    await _bill_single_item(tea["id"], 21.0)

    resp = await client.get(
        "/api/v1/reports/item-wise", params={"date_from": TODAY, "date_to": TODAY}, headers=headers
    )
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert [r["name_en"] for r in rows] == ["Meals", "Coffee", "Tea"]
    assert [r["category_name_en"] for r in rows] == ["Mains", "Beverages", "Beverages"]
    assert rows[0]["category_id"] == mains["id"]
    assert rows[1]["category_id"] == rows[2]["category_id"] == beverages["id"]


async def test_item_wise_export_uses_printer_columns_with_category_group_rows(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Production feedback round 4: CSV/Excel/PDF export shares the exact column format
    the printer version already uses — a single Name column (headers renamed Name/Qty/
    Sales, not the raw field-name dump Item Id/Name En/Name Ta/Quantity Sold/Revenue),
    with a category group-header row ahead of that category's items.
    """
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    await _create_tax_rule(client, headers)
    category = await _create_category(client, headers, "Mains")
    item = await _create_item(client, headers, category["id"], name_en="Meals", price=200)
    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "items": [{"item_id": item["id"], "quantity": 1}],
            },
            headers=headers,
        )
    ).json()
    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 210.0}]},
        headers=headers,
    )
    assert bill.status_code == 201, bill.text

    resp = await client.get(
        "/api/v1/reports/item-wise",
        params={"date_from": TODAY, "date_to": TODAY, "export": "csv"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    text = resp.content.decode("utf-8-sig")
    assert "Name,Qty,Sales" in text
    assert "Item Id" not in text
    assert "Quantity Sold" not in text
    assert "Mains" in text  # category group-header row
    assert "Meals" in text
    assert "TOTAL" in text


async def test_sales_summary_export_is_field_value_row_wise(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Same row-wise Field/Value shape the printer version already uses for Sales
    Summary/Tax Summary/Z-Report (production feedback round 4), not one wide row with a
    humanized column per field.
    """
    await _setup_one_bill(client, pro_max_tenant_admin)
    headers = pro_max_tenant_admin["headers"]

    resp = await client.get(
        "/api/v1/reports/sales-summary",
        params={"date_from": TODAY, "date_to": TODAY, "export": "csv"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    lines = resp.content.decode("utf-8-sig").strip().splitlines()
    assert lines[0] == "Field,Value"
    assert any(line.startswith("Total Bill Count,") for line in lines)
    assert any(line.startswith("Grand Total,") for line in lines)
    assert any(line.startswith("Payment - Cash,") for line in lines)
    assert any(line.startswith("Payment - UPI,") for line in lines)
    assert any(line.startswith("Payment - Card,") for line in lines)


async def test_cashier_wise_export_drops_login_id_matches_print_columns(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    ctx = await _setup_one_bill(client, pro_max_tenant_admin)
    headers = pro_max_tenant_admin["headers"]

    resp = await client.get(
        "/api/v1/reports/cashier-wise",
        params={"date_from": TODAY, "date_to": TODAY, "export": "csv"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    text = resp.content.decode("utf-8-sig")
    assert "Cashier Name,Bill Count,Sales" in text
    assert ctx["cashier"]["user"]["user_id"] not in text
    assert "Login Id" not in text


async def test_z_report_export_shows_payment_breakdown_rows(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    await _setup_one_bill(client, pro_max_tenant_admin)
    headers = pro_max_tenant_admin["headers"]

    resp = await client.get(
        "/api/v1/reports/z-report",
        params={"report_date": TODAY, "export": "csv"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    text = resp.content.decode("utf-8-sig")
    assert "Field,Value" in text
    assert "Payment - Cash,420.00" in text


async def test_tax_summary_reconciles(client: AsyncClient, tenant_admin: dict):
    await _setup_one_bill(client, tenant_admin)
    headers = tenant_admin["headers"]

    resp = await client.get(
        "/api/v1/reports/tax-summary", params={"date_from": TODAY, "date_to": TODAY}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["taxable_value"] == 400.0
    assert body["cgst_amount"] == 10.0
    assert body["sgst_amount"] == 10.0
    assert body["total_tax"] == 20.0


async def test_waiter_and_cashier_incentive_reports_both_populated_no_double_count(
    client: AsyncClient, tenant_admin: dict
):
    ctx = await _setup_one_bill(client, tenant_admin)
    headers = tenant_admin["headers"]

    waiter_sales = (
        await client.get(
            "/api/v1/reports/waiter-wise", params={"date_from": TODAY, "date_to": TODAY}, headers=headers
        )
    ).json()
    cashier_sales = (
        await client.get(
            "/api/v1/reports/cashier-wise", params={"date_from": TODAY, "date_to": TODAY}, headers=headers
        )
    ).json()
    waiter_incentive = (
        await client.get(
            "/api/v1/reports/waiter-incentive", params={"date_from": TODAY, "date_to": TODAY}, headers=headers
        )
    ).json()
    cashier_incentive = (
        await client.get(
            "/api/v1/reports/cashier-incentive",
            params={"date_from": TODAY, "date_to": TODAY},
            headers=headers,
        )
    ).json()

    # Same bill's net sale value (400) appears independently in both sales reports —
    # not summed into 800 anywhere.
    assert waiter_sales["rows"][0]["net_sale_value"] == 400.0
    assert cashier_sales["rows"][0]["net_sale_value"] == 400.0
    assert waiter_sales["total_net_sale_value"] == 400.0
    assert cashier_sales["total_net_sale_value"] == 400.0

    # Incentive amounts match rate x net_sale_value exactly, reconciling with the live
    # POS bill summary line computed the same way at finalize time (Phase 09).
    assert waiter_incentive["rows"][0]["waiter_id"] == ctx["waiter"]["id"]
    assert waiter_incentive["rows"][0]["incentive_amount"] == 8.0  # 2% of 400
    assert waiter_incentive["total_incentive_amount"] == 8.0

    assert cashier_incentive["rows"][0]["pos_user_id"] == ctx["cashier"]["user"]["id"]
    assert cashier_incentive["rows"][0]["incentive_amount"] == 4.0  # 1% of 400
    assert cashier_incentive["total_incentive_amount"] == 4.0

    assert ctx["bill"]["waiter_incentive_amount"] == 8.0
    assert ctx["bill"]["cashier_incentive_amount"] == 4.0


async def test_zero_incentive_rate_omitted_from_incentive_reports(client: AsyncClient, tenant_admin: dict):
    """A staff member with a 0% rate (not unset — an explicit 0) still gets a non-NULL
    but zero `incentive_amount` on the bill; the payout-worksheet report should drop
    them entirely rather than list a ₹0.00 row nobody needs to act on.
    """
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"])
    waiter = await _create_waiter(client, headers, location_id, incentive_rate=0)
    cashier = await _create_cashier(client, headers, local_handle="cashier00", incentive_rate=0)

    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "waiter_id": waiter["id"],
                "items": [{"item_id": item["id"], "quantity": 1}],
            },
            headers=cashier["headers"],
        )
    ).json()
    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 200.0}]},
        headers=cashier["headers"],
    )
    assert bill.status_code == 201, bill.text
    assert bill.json()["waiter_incentive_amount"] == 0.0
    assert bill.json()["cashier_incentive_amount"] == 0.0

    waiter_incentive = (
        await client.get(
            "/api/v1/reports/waiter-incentive", params={"date_from": TODAY, "date_to": TODAY}, headers=headers
        )
    ).json()
    cashier_incentive = (
        await client.get(
            "/api/v1/reports/cashier-incentive",
            params={"date_from": TODAY, "date_to": TODAY},
            headers=headers,
        )
    ).json()
    assert not any(r["waiter_id"] == waiter["id"] for r in waiter_incentive["rows"])
    assert not any(r["pos_user_id"] == cashier["user"]["id"] for r in cashier_incentive["rows"])


async def test_z_report_matches_sales_summary(client: AsyncClient, tenant_admin: dict):
    await _setup_one_bill(client, tenant_admin)
    headers = tenant_admin["headers"]

    resp = await client.get("/api/v1/reports/z-report", params={"report_date": TODAY}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["bill_count"] == 1
    assert body["grand_total"] == 420.0
    assert body["payments"] == [{"method": "cash", "amount": 420.0}]


async def test_waiter_role_blocked_from_all_reports(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    waiter_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w1", "name": "W1", "role": "waiter", "password": "password123"},
            headers=headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter_user["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    for path in (
        "sales-summary",
        "item-wise",
        "category-wise",
        "tax-summary",
        "waiter-wise",
        "cashier-wise",
        "waiter-incentive",
        "cashier-incentive",
    ):
        resp = await client.get(
            f"/api/v1/reports/{path}", params={"date_from": TODAY, "date_to": TODAY}, headers=waiter_headers
        )
        assert resp.status_code == 403, f"{path} should 403 for waiter"

    zresp = await client.get(
        "/api/v1/reports/z-report", params={"report_date": TODAY}, headers=waiter_headers
    )
    assert zresp.status_code == 403


async def test_export_gating_lite_pro_pro_max(
    client: AsyncClient, tenant_admin: dict, pro_tenant_admin: dict, pro_max_tenant_admin: dict
):
    await _setup_one_bill(client, tenant_admin)
    lite_resp = await client.get(
        "/api/v1/reports/sales-summary",
        params={"date_from": TODAY, "date_to": TODAY, "export": "csv"},
        headers=tenant_admin["headers"],
    )
    assert lite_resp.status_code == 403

    await _setup_one_bill(client, pro_tenant_admin)
    pro_csv = await client.get(
        "/api/v1/reports/sales-summary",
        params={"date_from": TODAY, "date_to": TODAY, "export": "csv"},
        headers=pro_tenant_admin["headers"],
    )
    assert pro_csv.status_code == 200
    assert pro_csv.headers["content-type"].startswith("text/csv")
    assert b"Bill Count" in pro_csv.content

    pro_pdf = await client.get(
        "/api/v1/reports/sales-summary",
        params={"date_from": TODAY, "date_to": TODAY, "export": "pdf"},
        headers=pro_tenant_admin["headers"],
    )
    assert pro_pdf.status_code == 403

    await _setup_one_bill(client, pro_max_tenant_admin)
    for fmt, content_type in (
        ("csv", "text/csv"),
        ("pdf", "application/pdf"),
        ("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ):
        resp = await client.get(
            "/api/v1/reports/item-wise",
            params={"date_from": TODAY, "date_to": TODAY, "export": fmt},
            headers=pro_max_tenant_admin["headers"],
        )
        assert resp.status_code == 200, f"{fmt}: {resp.text}"
        assert resp.headers["content-type"].startswith(content_type)
        assert len(resp.content) > 0
