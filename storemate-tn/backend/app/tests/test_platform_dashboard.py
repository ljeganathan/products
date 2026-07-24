from httpx import AsyncClient

from app.models.user import User
from app.services.subscription_service import EXTRA_STORE_PRICE_PAISE, EXTRA_USER_PRICE_PAISE
from app.tests.conftest import auth_headers, login


async def test_platform_dashboard_requires_product_owner(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        "/api/v1/platform/dashboard", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 403


async def test_platform_dashboard_mrr_and_plan_mix(
    client: AsyncClient,
    lite_tenant: dict,
    pro_tenant: dict,
    pro_max_tenant: dict,
    product_owner: User,
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    headers = auth_headers(owner_tokens["access_token"])

    # Give the Pro tenant one extra user and one extra store add-on so the
    # MRR sum has to account for add-on pricing, not just base plan price.
    subs_resp = await client.get(
        "/api/v1/platform/subscriptions",
        params={"tenant_id": str(pro_tenant["tenant"].id)},
        headers=headers,
    )
    pro_subscription_id = subs_resp.json()["items"][0]["id"]
    await client.patch(
        f"/api/v1/platform/subscriptions/{pro_subscription_id}",
        json={"extra_users": 1, "extra_stores": 1},
        headers=headers,
    )

    resp = await client.get("/api/v1/platform/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["active_tenant_count"] == 3

    expected_mrr = (
        lite_tenant["plan"].price_paise
        + pro_tenant["plan"].price_paise
        + EXTRA_USER_PRICE_PAISE
        + EXTRA_STORE_PRICE_PAISE
        + pro_max_tenant["plan"].price_paise
    )
    assert body["mrr_paise"] == expected_mrr

    plan_mix_by_code = {row["plan_code"]: row["tenant_count"] for row in body["plan_mix"]}
    assert plan_mix_by_code == {"lite": 1, "pro": 1, "pro_max": 1}


async def test_platform_dashboard_overdue_invoices_count(
    client: AsyncClient, lite_tenant: dict, product_owner: User
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    headers = auth_headers(owner_tokens["access_token"])

    subs_resp = await client.get(
        "/api/v1/platform/subscriptions",
        params={"tenant_id": str(lite_tenant["tenant"].id)},
        headers=headers,
    )
    subscription_id = subs_resp.json()["items"][0]["id"]

    generate_resp = await client.post(
        "/api/v1/platform/invoices/generate",
        json={"subscription_id": subscription_id},
        headers=headers,
    )
    invoice_id = generate_resp.json()["id"]
    await client.patch(
        f"/api/v1/platform/invoices/{invoice_id}", json={"status": "failed"}, headers=headers
    )

    resp = await client.get("/api/v1/platform/dashboard", headers=headers)
    assert resp.json()["overdue_invoices_count"] == 1


async def test_platform_dashboard_trialing_and_churned_counts(
    client: AsyncClient, lite_tenant: dict, product_owner: User
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    headers = auth_headers(owner_tokens["access_token"])

    tenant_id = str(lite_tenant["tenant"].id)
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}", json={"status": "trial"}, headers=headers
    )
    resp = await client.get("/api/v1/platform/dashboard", headers=headers)
    body = resp.json()
    assert body["trialing_count"] == 1
    assert body["active_tenant_count"] == 0

    await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}", json={"status": "cancelled"}, headers=headers
    )
    resp = await client.get("/api/v1/platform/dashboard", headers=headers)
    body = resp.json()
    assert body["churned_this_month_count"] == 1
    assert body["trialing_count"] == 0
