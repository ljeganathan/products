from httpx import AsyncClient

from app.tests.conftest import auth_headers, create_category_and_tax_profile, login


async def _create_item(client: AsyncClient, headers: dict) -> str:
    category_id, tax_profile_id = await create_category_and_tax_profile(client, headers)
    resp = await client.post(
        "/api/v1/items",
        json={
            "category_id": category_id,
            "name_en": "Sugar 1kg",
            "name_ta": "சர்க்கரை 1kg",
            "unit": "kg",
            "mrp_paise": 5000,
            "selling_price_paise": 4800,
            "cost_price_paise": 4000,
            "tax_profile_id": tax_profile_id,
            "reorder_level": 5,
        },
        headers=headers,
    )
    return resp.json()["id"]


async def test_adjust_stock_purchase_then_sale(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers)

    purchase = await client.post(
        "/api/v1/stock/adjust",
        json={"item_id": item_id, "change_qty": 10, "reason": "purchase"},
        headers=headers,
    )
    assert purchase.status_code == 201, purchase.text
    assert purchase.json()["quantity_on_hand"] == 10

    sale = await client.post(
        "/api/v1/stock/adjust",
        json={"item_id": item_id, "change_qty": -4, "reason": "sale"},
        headers=headers,
    )
    assert sale.status_code == 201
    assert sale.json()["quantity_on_hand"] == 6


async def test_adjust_stock_below_zero_rejected(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers)

    resp = await client.post(
        "/api/v1/stock/adjust",
        json={"item_id": item_id, "change_qty": -1, "reason": "sale"},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_stock_list_shows_quantity_and_low_stock_flag(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers)  # reorder_level = 5

    await client.post(
        "/api/v1/stock/adjust",
        json={"item_id": item_id, "change_qty": 3, "reason": "purchase"},
        headers=headers,
    )

    resp = await client.get("/api/v1/stock", headers=headers)
    assert resp.status_code == 200
    row = next(r for r in resp.json()["items"] if r["item_id"] == item_id)
    assert row["quantity_on_hand"] == 3
    assert row["low_stock"] is True


async def test_stock_movements_recorded(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    item_id = await _create_item(client, headers)

    await client.post(
        "/api/v1/stock/adjust",
        json={"item_id": item_id, "change_qty": 10, "reason": "purchase"},
        headers=headers,
    )
    await client.post(
        "/api/v1/stock/adjust",
        json={"item_id": item_id, "change_qty": -2, "reason": "sale"},
        headers=headers,
    )

    resp = await client.get("/api/v1/stock/movements", params={"item_id": item_id}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


async def test_low_stock_endpoint_gated_by_plan(
    client: AsyncClient, lite_tenant: dict, pro_tenant: dict
) -> None:
    lite_tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    lite_resp = await client.get(
        "/api/v1/stock/low-stock", headers=auth_headers(lite_tokens["access_token"])
    )
    assert lite_resp.status_code == 403

    pro_tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    pro_resp = await client.get(
        "/api/v1/stock/low-stock", headers=auth_headers(pro_tokens["access_token"])
    )
    assert pro_resp.status_code == 200
