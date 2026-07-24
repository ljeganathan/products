from datetime import date, timedelta

from httpx import AsyncClient

from app.tests.conftest import auth_headers, create_category_and_tax_profile, login


async def _create_item(
    client: AsyncClient,
    headers: dict,
    *,
    selling_price_paise: int = 10_000,
    opening_stock: float = 50,
    reorder_level: float = 5,
) -> str:
    category_id, tax_profile_id = await create_category_and_tax_profile(client, headers)
    resp = await client.post(
        "/api/v1/items",
        json={
            "category_id": category_id,
            "name_en": "Dashboard Test Item",
            "name_ta": "டாஷ்போர்டு பரிசோதனை பொருள்",
            "unit": "pcs",
            "mrp_paise": selling_price_paise + 1_000,
            "selling_price_paise": selling_price_paise,
            "cost_price_paise": selling_price_paise - 2_000,
            "tax_profile_id": tax_profile_id,
            "opening_stock": opening_stock,
            "reorder_level": reorder_level,
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


async def test_summary_totals_match_created_bills(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers, selling_price_paise=10_000, opening_stock=50)

    bill1 = await _create_bill(client, headers, item_id, 2)
    bill2 = await _create_bill(client, headers, item_id, 1)

    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["bill_count"] == 2
    assert body["total_paise"] == bill1["total_paise"] + bill2["total_paise"]
    assert body["avg_bill_paise"] == round((bill1["total_paise"] + bill2["total_paise"]) / 2)
    assert body["top_items"][0]["name"] == "Dashboard Test Item"


async def test_low_stock_count_zero_on_lite_nonzero_on_pro(
    client: AsyncClient, lite_tenant: dict, pro_tenant: dict
) -> None:
    lite_tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    lite_headers = auth_headers(lite_tokens["access_token"])
    await _create_item(client, lite_headers, opening_stock=2, reorder_level=5)

    lite_resp = await client.get("/api/v1/dashboard/summary", headers=lite_headers)
    assert lite_resp.json()["low_stock_count"] == 0

    pro_tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    pro_headers = auth_headers(pro_tokens["access_token"])
    await _create_item(client, pro_headers, opening_stock=2, reorder_level=5)

    pro_resp = await client.get("/api/v1/dashboard/summary", headers=pro_headers)
    assert pro_resp.json()["low_stock_count"] == 1


async def test_trend_and_breakdown_gated_by_plan_tier(
    client: AsyncClient, lite_tenant: dict, pro_tenant: dict
) -> None:
    today = date.today().isoformat()

    lite_tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    lite_headers = auth_headers(lite_tokens["access_token"])
    lite_trend = await client.get(
        "/api/v1/dashboard/trend",
        params={"date_from": today, "date_to": today},
        headers=lite_headers,
    )
    assert lite_trend.status_code == 403
    lite_breakdown = await client.get(
        "/api/v1/dashboard/breakdown",
        params={"by": "payment_mode", "date_from": today, "date_to": today},
        headers=lite_headers,
    )
    assert lite_breakdown.status_code == 403

    pro_tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    pro_headers = auth_headers(pro_tokens["access_token"])
    item_id = await _create_item(client, pro_headers)
    await _create_bill(client, pro_headers, item_id, 1)

    pro_trend = await client.get(
        "/api/v1/dashboard/trend",
        params={"date_from": today, "date_to": today},
        headers=pro_headers,
    )
    assert pro_trend.status_code == 200
    assert pro_trend.json()[0]["bill_count"] == 1

    pro_breakdown = await client.get(
        "/api/v1/dashboard/breakdown",
        params={"by": "payment_mode", "date_from": today, "date_to": today},
        headers=pro_headers,
    )
    assert pro_breakdown.status_code == 200
    assert pro_breakdown.json()[0]["label"] == "cash"


async def test_category_breakdown_attributes_at_line_item_level(
    client: AsyncClient, pro_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers, selling_price_paise=5_000)
    await _create_bill(client, headers, item_id, 3)

    today = date.today().isoformat()
    resp = await client.get(
        "/api/v1/dashboard/breakdown",
        params={"by": "category", "date_from": today, "date_to": today},
        headers=headers,
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["label"] == "Beverages"  # create_category_and_tax_profile's fixed category


async def test_stores_and_export_gated_to_pro_max_only(
    client: AsyncClient, pro_tenant: dict, pro_max_tenant: dict
) -> None:
    today = date.today().isoformat()

    pro_tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    pro_headers = auth_headers(pro_tokens["access_token"])
    pro_stores_resp = await client.get(
        "/api/v1/dashboard/stores",
        params={"date_from": today, "date_to": today},
        headers=pro_headers,
    )
    assert pro_stores_resp.status_code == 403
    pro_export_resp = await client.get(
        "/api/v1/dashboard/export.pdf",
        params={"date_from": today, "date_to": today},
        headers=pro_headers,
    )
    assert pro_export_resp.status_code == 403

    pro_max_tokens = await login(client, "admin@tenantpromax.dev", "Admin@123")
    pro_max_headers = auth_headers(pro_max_tokens["access_token"])
    item_id = await _create_item(client, pro_max_headers)
    await _create_bill(client, pro_max_headers, item_id, 1)

    stores_resp = await client.get(
        "/api/v1/dashboard/stores",
        params={"date_from": today, "date_to": today},
        headers=pro_max_headers,
    )
    assert stores_resp.status_code == 200
    stores = stores_resp.json()
    assert len(stores) == 1
    assert stores[0]["bill_count"] == 1

    export_resp = await client.get(
        "/api/v1/dashboard/export.pdf",
        params={
            "date_from": (date.today() - timedelta(days=7)).isoformat(),
            "date_to": today,
        },
        headers=pro_max_headers,
    )
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"] == "application/pdf"
    assert export_resp.content.startswith(b"%PDF")
