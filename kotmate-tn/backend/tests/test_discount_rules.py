import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_flat_percent_rule(client: AsyncClient, tenant_admin: dict):
    resp = await client.post(
        "/api/v1/discount-rules",
        json={"name": "Festival Offer", "type": "flat_percent", "value": 10},
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["type"] == "flat_percent"


async def test_coupon_requires_code(client: AsyncClient, tenant_admin: dict):
    resp = await client.post(
        "/api/v1/discount-rules",
        json={"name": "No code", "type": "coupon", "value": 10},
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 422


async def test_coupon_code_unique_per_tenant(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    payload = {"name": "Save10", "type": "coupon", "value": 10, "coupon_code": "SAVE10"}
    first = await client.post("/api/v1/discount-rules", json=payload, headers=headers)
    assert first.status_code == 201

    dup = await client.post("/api/v1/discount-rules", json=payload, headers=headers)
    assert dup.status_code == 400


async def test_invalid_type_rejected(client: AsyncClient, tenant_admin: dict):
    resp = await client.post(
        "/api/v1/discount-rules",
        json={"name": "Bad", "type": "buy_one_get_one"},
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 422


async def test_non_tenant_admin_can_read_but_not_write_discount_rules(
    client: AsyncClient, tenant_admin: dict
):
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

    assert (await client.get("/api/v1/discount-rules", headers=waiter_headers)).status_code == 200
    create_resp = await client.post(
        "/api/v1/discount-rules",
        json={"name": "Blocked", "type": "flat_percent", "value": 5},
        headers=waiter_headers,
    )
    assert create_resp.status_code == 403
