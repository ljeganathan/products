import csv
import io
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.tests.conftest import (
    auth_headers,
    create_category_and_tax_profile,
    create_pos_user,
    login,
)


async def _create_item(
    client: AsyncClient, headers: dict, *, selling_price_paise: int = 10_000
) -> str:
    category_id, tax_profile_id = await create_category_and_tax_profile(client, headers)
    resp = await client.post(
        "/api/v1/items",
        json={
            "category_id": category_id,
            "name_en": "Report Test Item",
            "name_ta": "அறிக்கை பரிசோதனை பொருள்",
            "unit": "pcs",
            "mrp_paise": selling_price_paise + 1_000,
            "selling_price_paise": selling_price_paise,
            "cost_price_paise": selling_price_paise - 2_000,
            "tax_profile_id": tax_profile_id,
            "opening_stock": 100,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_bill(client: AsyncClient, headers: dict, item_id: str, qty: float) -> dict:
    resp = await client.post(
        "/api/v1/bills",
        json={"payment_mode": "cash", "items": [{"item_id": item_id, "qty": qty}]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_sales_report_totals_match_created_bills(
    client: AsyncClient, pro_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers)
    bill1 = await _create_bill(client, headers, item_id, 2)
    bill2 = await _create_bill(client, headers, item_id, 1)

    today = date.today().isoformat()
    resp = await client.get(
        "/api/v1/reports/sales",
        params={"date_from": today, "date_to": today},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["range_clamped"] is False
    assert body["bill_count"] == 2
    assert body["total_paise"] == bill1["total_paise"] + bill2["total_paise"]
    assert body["daily"][0]["bill_count"] == 2


async def test_sales_report_profit_uses_item_cost_price(
    client: AsyncClient, pro_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    # selling_price_paise=10_000, cost_price_paise defaults to selling - 2_000 = 8_000
    item_id = await _create_item(client, headers)
    await _create_bill(client, headers, item_id, 2)
    await _create_bill(client, headers, item_id, 1)

    today = date.today().isoformat()
    resp = await client.get(
        "/api/v1/reports/sales",
        params={"date_from": today, "date_to": today},
        headers=headers,
    )
    assert resp.status_code == 200
    # profit per unit = 10_000 - 8_000 = 2_000 paise; qty 2 + 1 = 3 units sold
    assert resp.json()["profit_paise"] == 3 * 2_000


async def test_gst_summary_matches_persisted_bill_columns(
    client: AsyncClient, pro_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers)
    bill = await _create_bill(client, headers, item_id, 2)

    today = date.today().isoformat()
    resp = await client.get(
        "/api/v1/reports/gst-summary",
        params={"date_from": today, "date_to": today},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cgst_paise"] == bill["cgst_paise"]
    assert body["sgst_paise"] == bill["sgst_paise"]
    assert body["subtotal_paise"] == bill["subtotal_paise"]
    assert body["total_paise"] == bill["total_paise"]


async def test_lite_plan_clamps_range_to_today(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers)
    await _create_bill(client, headers, item_id, 1)

    week_ago = (date.today() - timedelta(days=7)).isoformat()
    today = date.today().isoformat()
    resp = await client.get(
        "/api/v1/reports/sales",
        params={"date_from": week_ago, "date_to": today},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["range_clamped"] is True
    assert body["date_from"] == today
    assert body["date_to"] == today


async def test_csv_export_blocked_on_lite_and_works_on_pro(
    client: AsyncClient, lite_tenant: dict, pro_tenant: dict
) -> None:
    lite_tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    lite_resp = await client.get(
        "/api/v1/reports/sales.csv", headers=auth_headers(lite_tokens["access_token"])
    )
    assert lite_resp.status_code == 403

    pro_tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    pro_headers = auth_headers(pro_tokens["access_token"])
    item_id = await _create_item(client, pro_headers, selling_price_paise=20_000)
    bill = await _create_bill(client, pro_headers, item_id, 1)

    today = date.today().isoformat()
    csv_resp = await client.get(
        "/api/v1/reports/sales.csv",
        params={"date_from": today, "date_to": today},
        headers=pro_headers,
    )
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")

    rows = list(csv.reader(io.StringIO(csv_resp.text)))
    assert rows[0][0] == "Bill #"
    data_row = rows[1]
    assert int(data_row[0]) == bill["bill_number"]
    assert data_row[9] == f"{bill['total_paise'] / 100:.2f}"


async def test_pos_user_only_sees_own_bills_in_report(
    client: AsyncClient, pro_tenant: dict, db_session: AsyncSession
) -> None:
    tenant = pro_tenant["tenant"]
    store = pro_tenant["store"]
    admin_tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    admin_headers = auth_headers(admin_tokens["access_token"])
    item_id = await _create_item(client, admin_headers)
    await _create_bill(client, admin_headers, item_id, 1)

    await create_pos_user(
        db_session,
        tenant_id=tenant.id,
        store_id=store.id,
        email="cashier@tenantpro.dev",
        password="Cashier@123",
    )
    await db_session.commit()
    cashier_tokens = await login(client, "cashier@tenantpro.dev", "Cashier@123")
    cashier_headers = auth_headers(cashier_tokens["access_token"])
    await _create_bill(client, cashier_headers, item_id, 1)

    today = date.today().isoformat()
    cashier_report = await client.get(
        "/api/v1/reports/sales",
        params={"date_from": today, "date_to": today},
        headers=cashier_headers,
    )
    assert cashier_report.json()["bill_count"] == 1

    admin_report = await client.get(
        "/api/v1/reports/sales",
        params={"date_from": today, "date_to": today},
        headers=admin_headers,
    )
    assert admin_report.json()["bill_count"] == 2
