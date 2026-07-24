from httpx import AsyncClient

from app.models.user import User
from app.tests.conftest import auth_headers, login


async def test_list_tenants_requires_product_owner(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        "/api/v1/platform/tenants", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 403


async def test_list_tenants_shows_usage_vs_plan_limits(
    client: AsyncClient, lite_tenant: dict, product_owner: User
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    resp = await client.get(
        "/api/v1/platform/tenants", headers=auth_headers(owner_tokens["access_token"])
    )
    assert resp.status_code == 200
    row = next(t for t in resp.json()["items"] if t["name"] == "Tenant A")
    assert row["plan_code"] == "lite"
    assert row["usage"]["users_count"] == 1
    assert row["usage"]["users_limit"] == 2
    assert row["usage"]["stores_count"] == 1
    assert row["usage"]["stores_limit"] == 1
    assert row["has_pending_upgrade_request"] is False


async def test_create_tenant_end_to_end(
    client: AsyncClient, product_owner: User, all_plans: dict
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    resp = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "New Kirana Store",
            "owner_email": "owner@newkirana.dev",
            "owner_phone": "+919999999999",
            "plan_code": "lite",
            "admin_name": "New Admin",
            "admin_email": "admin@newkirana.dev",
            "admin_password": "Admin@1234",
        },
        headers=auth_headers(owner_tokens["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["plan_code"] == "lite"
    assert body["usage"]["users_count"] == 1

    # The freshly created admin can actually log in and use the API.
    admin_tokens = await login(client, "admin@newkirana.dev", "Admin@1234")
    me = await client.get(
        "/api/v1/auth/me", headers=auth_headers(admin_tokens["access_token"])
    )
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


async def test_create_tenant_duplicate_owner_email_conflicts(
    client: AsyncClient, lite_tenant: dict, product_owner: User
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    resp = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Duplicate Tenant",
            "owner_email": lite_tenant["tenant"].owner_email,
            "owner_phone": "+919999999998",
            "plan_code": "lite",
            "admin_name": "Admin",
            "admin_email": "admin@duplicate.dev",
            "admin_password": "Admin@1234",
        },
        headers=auth_headers(owner_tokens["access_token"]),
    )
    assert resp.status_code == 409


async def test_suspend_blocks_login_and_reactivate_restores_it(
    client: AsyncClient, lite_tenant: dict, product_owner: User
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    owner_headers = auth_headers(owner_tokens["access_token"])

    tenant_id = str(lite_tenant["tenant"].id)
    suspend_resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}",
        json={"status": "suspended"},
        headers=owner_headers,
    )
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["status"] == "suspended"

    blocked = await client.post(
        "/api/v1/auth/login", json={"email": "admin@tenanta.dev", "password": "Admin@123"}
    )
    assert blocked.status_code == 403

    reactivate_resp = await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}",
        json={"status": "active"},
        headers=owner_headers,
    )
    assert reactivate_resp.status_code == 200

    restored = await client.post(
        "/api/v1/auth/login", json={"email": "admin@tenanta.dev", "password": "Admin@123"}
    )
    assert restored.status_code == 200
