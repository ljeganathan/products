from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.tests.conftest import auth_headers, create_pos_user, login


async def test_create_category_happy_path(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.post(
        "/api/v1/categories",
        json={"name_en": "Dairy", "name_ta": "பால் பொருட்கள்"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name_en"] == "Dairy"
    assert body["parent_category_id"] is None


async def test_create_sub_category_with_parent(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    parent_resp = await client.post(
        "/api/v1/categories", json={"name_en": "Dairy", "name_ta": "பால்"}, headers=headers
    )
    parent_id = parent_resp.json()["id"]

    child_resp = await client.post(
        "/api/v1/categories",
        json={"name_en": "Milk", "name_ta": "பால்", "parent_category_id": parent_id},
        headers=headers,
    )
    assert child_resp.status_code == 201, child_resp.text
    assert child_resp.json()["parent_category_id"] == parent_id


async def test_create_category_invalid_parent_fails(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.post(
        "/api/v1/categories",
        json={
            "name_en": "Milk",
            "name_ta": "பால்",
            "parent_category_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 400


async def test_pos_user_can_read_but_not_write_categories(
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

    list_resp = await client.get("/api/v1/categories", headers=headers)
    assert list_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/categories", json={"name_en": "Dairy", "name_ta": "பால்"}, headers=headers
    )
    assert create_resp.status_code == 403


async def test_category_tenant_isolation(
    client: AsyncClient, lite_tenant: dict, db_session: AsyncSession
) -> None:
    from app.models.enums import PlanCode
    from app.tests.conftest import create_tenant_with_admin

    await create_tenant_with_admin(
        db_session,
        plan_code=PlanCode.PRO,
        max_users=5,
        tenant_name="Tenant B Categories",
        admin_email="admin@tenantbcat.dev",
        admin_password="Admin@123",
    )
    tokens_b = await login(client, "admin@tenantbcat.dev", "Admin@123")
    category_b = await client.post(
        "/api/v1/categories",
        json={"name_en": "Snacks", "name_ta": "சிற்றுண்டி"},
        headers=auth_headers(tokens_b["access_token"]),
    )
    category_b_id = category_b.json()["id"]

    tokens_a = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        f"/api/v1/categories/{category_b_id}", headers=auth_headers(tokens_a["access_token"])
    )
    assert resp.status_code == 404
