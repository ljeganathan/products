from httpx import AsyncClient

from app.models.user import User
from app.tests.conftest import auth_headers, login


async def test_list_plans_requires_product_owner(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get("/api/v1/platform/plans", headers=auth_headers(tokens["access_token"]))
    assert resp.status_code == 403


async def test_update_plan_price_and_limits(
    client: AsyncClient, pro_tenant: dict, product_owner: User
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    headers = auth_headers(owner_tokens["access_token"])

    list_resp = await client.get("/api/v1/platform/plans", headers=headers)
    pro_plan = next(p for p in list_resp.json() if p["code"] == "pro")

    update_resp = await client.patch(
        f"/api/v1/platform/plans/{pro_plan['id']}",
        json={"price_paise": 249_900, "max_users": 8},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["price_paise"] == 249_900
    assert update_resp.json()["max_users"] == 8

    # Effective immediately for the tenant already on this plan — no code
    # deploy needed to raise its limit (CLAUDE.md §4).
    admin_tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    for i in range(4):
        resp = await client.post(
            "/api/v1/users",
            json={
                "name": "Cashier",
                "email": f"newcashier{i}@tenantpro.dev",
                "password": "Cashier@123",
                "role": "pos_user",
            },
            headers=auth_headers(admin_tokens["access_token"]),
        )
        assert resp.status_code == 201, resp.text
