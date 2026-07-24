import io

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.tests.conftest import (
    auth_headers,
    create_category_and_tax_profile,
    create_pos_user,
    login,
)


async def test_create_item_happy_path(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    category_id, tax_profile_id = await create_category_and_tax_profile(client, headers)

    resp = await client.post(
        "/api/v1/items",
        json={
            "category_id": category_id,
            "name_en": "Amul Milk 500ml",
            "name_ta": "அமுல் பால் 500ml",
            "barcode": "8901234567890",
            "unit": "pack",
            "mrp_paise": 3000,
            "selling_price_paise": 2800,
            "cost_price_paise": 2500,
            "tax_profile_id": tax_profile_id,
            "opening_stock": 10,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["barcode"] == "8901234567890"
    assert body["is_active"] is True


async def test_barcode_uniqueness_enforced_per_tenant(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    category_id, tax_profile_id = await create_category_and_tax_profile(client, headers)

    item_payload = {
        "category_id": category_id,
        "name_en": "Parle-G",
        "name_ta": "பார்லே-ஜி",
        "barcode": "1111111111111",
        "unit": "pack",
        "mrp_paise": 1000,
        "selling_price_paise": 1000,
        "cost_price_paise": 800,
        "tax_profile_id": tax_profile_id,
    }
    first = await client.post("/api/v1/items", json=item_payload, headers=headers)
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/items",
        json={**item_payload, "name_en": "Parle-G Duplicate"},
        headers=headers,
    )
    assert second.status_code == 409


async def test_barcode_exact_lookup(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    category_id, tax_profile_id = await create_category_and_tax_profile(client, headers)

    await client.post(
        "/api/v1/items",
        json={
            "category_id": category_id,
            "name_en": "Tata Salt",
            "name_ta": "டாடா உப்பு",
            "barcode": "9998887776665",
            "unit": "pack",
            "mrp_paise": 2500,
            "selling_price_paise": 2400,
            "cost_price_paise": 2000,
            "tax_profile_id": tax_profile_id,
        },
        headers=headers,
    )

    resp = await client.get("/api/v1/items", params={"barcode": "9998887776665"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name_en"] == "Tata Salt"

    miss = await client.get("/api/v1/items", params={"barcode": "0000000000000"}, headers=headers)
    assert miss.json()["total"] == 0


async def test_bulk_import_reports_bad_rows_without_failing_whole_import(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    category_id, tax_profile_id = await create_category_and_tax_profile(client, headers)

    cat_resp = await client.get(f"/api/v1/categories/{category_id}", headers=headers)
    category_name = cat_resp.json()["name_en"]
    tax_resp = await client.get("/api/v1/settings/tax-profiles", headers=headers)
    tax_name = next(t["name"] for t in tax_resp.json() if t["id"] == tax_profile_id)

    columns = [
        "name_en", "name_ta", "category", "brand", "pack_size", "barcode", "sku", "unit",
        "mrp", "selling_price", "cost_price", "tax_profile", "hsn_code",
        "reorder_level", "reorder_qty", "opening_stock",
    ]
    rows = []
    for i in range(97):
        rows.append(
            [
                f"Item {i}", f"பொருள் {i}", category_name, "BrandX", "1kg", f"{1000000000000 + i}",
                f"SKU{i}", "pcs", "10.00", "12.00", "8.00", tax_name, "1905", "5", "10", "20",
            ]
        )
    # 3 intentionally bad rows: missing name_en, invalid unit, unknown category.
    rows.append(
        ["", "பொருள் பாட்", category_name, "", "", "", "", "pcs", "10", "12", "8", tax_name, "", "0",
         "0", "0"]
    )
    rows.append(
        ["Bad Unit Item", "பொருள்", category_name, "", "", "", "", "not-a-unit", "10", "12", "8",
         tax_name, "", "0", "0", "0"]
    )
    rows.append(
        ["Unknown Cat Item", "பொருள்", "Nonexistent Category", "", "", "", "", "pcs", "10", "12",
         "8", tax_name, "", "0", "0", "0"]
    )

    csv_lines = [",".join(columns)]
    for row in rows:
        csv_lines.append(",".join(f'"{v}"' for v in row))
    csv_content = "\n".join(csv_lines)

    files = {"file": ("items.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    resp = await client.post("/api/v1/items/bulk-import", files=files, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rows"] == 100
    assert body["created_count"] == 97
    assert body["error_count"] == 3
    assert len(body["errors"]) == 3


async def test_tenant_isolation_on_item_fetch(
    client: AsyncClient, lite_tenant: dict, db_session: AsyncSession
) -> None:
    from app.models.enums import PlanCode
    from app.tests.conftest import create_tenant_with_admin

    await create_tenant_with_admin(
        db_session,
        plan_code=PlanCode.PRO,
        max_users=5,
        tenant_name="Tenant B Items",
        admin_email="admin@tenantbitems.dev",
        admin_password="Admin@123",
    )
    tokens_b = await login(client, "admin@tenantbitems.dev", "Admin@123")
    headers_b = auth_headers(tokens_b["access_token"])
    category_id, tax_profile_id = await create_category_and_tax_profile(client, headers_b)
    item_resp = await client.post(
        "/api/v1/items",
        json={
            "category_id": category_id,
            "name_en": "Tenant B Item",
            "name_ta": "பொருள் பி",
            "unit": "pcs",
            "mrp_paise": 100,
            "selling_price_paise": 100,
            "cost_price_paise": 80,
            "tax_profile_id": tax_profile_id,
        },
        headers=headers_b,
    )
    item_id = item_resp.json()["id"]

    tokens_a = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        f"/api/v1/items/{item_id}", headers=auth_headers(tokens_a["access_token"])
    )
    assert resp.status_code == 404


async def test_pos_user_read_only_on_items(
    client: AsyncClient, lite_tenant: dict, db_session: AsyncSession
) -> None:
    tenant = lite_tenant["tenant"]
    store = lite_tenant["store"]
    await create_pos_user(
        db_session,
        tenant_id=tenant.id,
        store_id=store.id,
        email="cashier@tenanta.dev",
        password="Cashier@123",
    )
    tokens = await login(client, "cashier@tenanta.dev", "Cashier@123")
    headers = auth_headers(tokens["access_token"])

    list_resp = await client.get("/api/v1/items", headers=headers)
    assert list_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/items",
        json={
            "category_id": "00000000-0000-0000-0000-000000000000",
            "name_en": "x",
            "name_ta": "x",
            "unit": "pcs",
            "mrp_paise": 1,
            "selling_price_paise": 1,
            "cost_price_paise": 1,
            "tax_profile_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=headers,
    )
    assert create_resp.status_code == 403
