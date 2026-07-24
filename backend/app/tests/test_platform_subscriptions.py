from httpx import AsyncClient

from app.models.user import User
from app.tests.conftest import auth_headers, login


async def test_list_subscriptions_requires_product_owner(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        "/api/v1/platform/subscriptions", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 403


async def test_change_plan_immediately_changes_tenant_access(
    client: AsyncClient, lite_tenant: dict, product_owner: User, all_plans: dict
) -> None:
    admin_tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    admin_headers = auth_headers(admin_tokens["access_token"])

    # Still on Lite: low-stock is gated off.
    before = await client.get("/api/v1/stock/low-stock", headers=admin_headers)
    assert before.status_code == 403

    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    owner_headers = auth_headers(owner_tokens["access_token"])

    subs_resp = await client.get(
        "/api/v1/platform/subscriptions",
        params={"tenant_id": str(lite_tenant["tenant"].id)},
        headers=owner_headers,
    )
    subscription_id = subs_resp.json()["items"][0]["id"]

    plans_resp = await client.get("/api/v1/platform/plans", headers=owner_headers)
    pro_plan_id = next(p["id"] for p in plans_resp.json() if p["code"] == "pro")

    change_resp = await client.patch(
        f"/api/v1/platform/subscriptions/{subscription_id}/change-plan",
        json={"plan_id": pro_plan_id},
        headers=owner_headers,
    )
    assert change_resp.status_code == 200, change_resp.text
    assert change_resp.json()["plan_code"] == "pro"

    # Same admin token, no re-login — the very next request already sees Pro
    # access, because plan_limits re-reads the active subscription every call.
    after = await client.get("/api/v1/stock/low-stock", headers=admin_headers)
    assert after.status_code == 200


async def test_downgrade_blocked_when_usage_exceeds_target_plan(
    client: AsyncClient, pro_tenant: dict, product_owner: User, all_plans: dict
) -> None:
    admin_tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    admin_headers = auth_headers(admin_tokens["access_token"])

    # Pro allows 5 users; bring the tenant to 3 active users (over Lite's max_users=2).
    for i in range(2):
        resp = await client.post(
            "/api/v1/users",
            json={
                "name": "Cashier",
                "email": f"cashier{i}@tenantpro.dev",
                "password": "Cashier@123",
                "role": "pos_user",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201

    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    owner_headers = auth_headers(owner_tokens["access_token"])

    subs_resp = await client.get(
        "/api/v1/platform/subscriptions",
        params={"tenant_id": str(pro_tenant["tenant"].id)},
        headers=owner_headers,
    )
    subscription_id = subs_resp.json()["items"][0]["id"]

    plans_resp = await client.get("/api/v1/platform/plans", headers=owner_headers)
    lite_plan_id = next(p["id"] for p in plans_resp.json() if p["code"] == "lite")

    downgrade_resp = await client.patch(
        f"/api/v1/platform/subscriptions/{subscription_id}/change-plan",
        json={"plan_id": lite_plan_id},
        headers=owner_headers,
    )
    assert downgrade_resp.status_code == 409
    assert "exceed" in downgrade_resp.json()["detail"].lower()

    # Nothing changed — the tenant is still on Pro.
    still_pro = await client.get(
        "/api/v1/platform/subscriptions",
        params={"tenant_id": str(pro_tenant["tenant"].id)},
        headers=owner_headers,
    )
    assert still_pro.json()["items"][0]["plan_code"] == "pro"


async def test_tenant_upgrade_request_visible_and_resolved_by_change_plan(
    client: AsyncClient, lite_tenant: dict, product_owner: User, all_plans: dict
) -> None:
    admin_tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    admin_headers = auth_headers(admin_tokens["access_token"])

    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    owner_headers = auth_headers(owner_tokens["access_token"])

    plans_resp = await client.get("/api/v1/platform/plans", headers=owner_headers)
    pro_plan_id = next(p["id"] for p in plans_resp.json() if p["code"] == "pro")

    request_resp = await client.post(
        "/api/v1/settings/subscription/upgrade-request",
        json={"plan_id": pro_plan_id},
        headers=admin_headers,
    )
    assert request_resp.status_code == 201
    assert request_resp.json()["requested_plan_code"] == "pro"

    tenants_resp = await client.get("/api/v1/platform/tenants", headers=owner_headers)
    row = next(t for t in tenants_resp.json()["items"] if t["name"] == "Tenant A")
    assert row["has_pending_upgrade_request"] is True

    subs_resp = await client.get(
        "/api/v1/platform/subscriptions",
        params={"tenant_id": str(lite_tenant["tenant"].id)},
        headers=owner_headers,
    )
    subscription_id = subs_resp.json()["items"][0]["id"]

    await client.patch(
        f"/api/v1/platform/subscriptions/{subscription_id}/change-plan",
        json={"plan_id": pro_plan_id},
        headers=owner_headers,
    )

    resolved = await client.get("/api/v1/platform/tenants", headers=owner_headers)
    row = next(t for t in resolved.json()["items"] if t["name"] == "Tenant A")
    assert row["has_pending_upgrade_request"] is False
