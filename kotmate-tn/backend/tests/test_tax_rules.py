import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_and_list_tax_rule(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    resp = await client.post(
        "/api/v1/tax-rules",
        json={"name": "Standard GST", "cgst_rate": 2.5, "sgst_rate": 2.5, "is_default": True},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["is_default"] is True
    assert body["is_active"] is True

    list_resp = await client.get("/api/v1/tax-rules", headers=headers)
    assert any(r["id"] == body["id"] for r in list_resp.json())


async def test_only_one_default_tax_rule_per_tenant(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    first = (
        await client.post(
            "/api/v1/tax-rules",
            json={"name": "Rate A", "cgst_rate": 2.5, "sgst_rate": 2.5, "is_default": True},
            headers=headers,
        )
    ).json()
    second = (
        await client.post(
            "/api/v1/tax-rules",
            json={"name": "Rate B", "cgst_rate": 9, "sgst_rate": 9, "is_default": True},
            headers=headers,
        )
    ).json()
    assert second["is_default"] is True

    refetched_first = next(
        r for r in (await client.get("/api/v1/tax-rules", headers=headers)).json() if r["id"] == first["id"]
    )
    assert refetched_first["is_default"] is False


async def test_invalid_rate_rejected(client: AsyncClient, tenant_admin: dict):
    resp = await client.post(
        "/api/v1/tax-rules",
        json={"name": "Bad", "cgst_rate": 150, "sgst_rate": 2.5},
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 422


async def test_non_tenant_admin_can_read_but_not_write_tax_rules(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    waiter = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w1", "name": "W1", "role": "waiter", "password": "password123"},
            headers=headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert (await client.get("/api/v1/tax-rules", headers=waiter_headers)).status_code == 200
    create_resp = await client.post(
        "/api/v1/tax-rules",
        json={"name": "Blocked", "cgst_rate": 2.5, "sgst_rate": 2.5},
        headers=waiter_headers,
    )
    assert create_resp.status_code == 403


async def test_update_tax_rule_deactivate(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    created = (
        await client.post(
            "/api/v1/tax-rules",
            json={"name": "Rate", "cgst_rate": 2.5, "sgst_rate": 2.5},
            headers=headers,
        )
    ).json()
    update_resp = await client.patch(
        f"/api/v1/tax-rules/{created['id']}", json={"is_active": False}, headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False
