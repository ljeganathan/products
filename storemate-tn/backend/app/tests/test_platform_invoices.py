from httpx import AsyncClient

from app.models.user import User
from app.tests.conftest import auth_headers, login


async def _get_subscription_id(client: AsyncClient, headers: dict, tenant_id: str) -> str:
    resp = await client.get(
        "/api/v1/platform/subscriptions", params={"tenant_id": tenant_id}, headers=headers
    )
    return resp.json()["items"][0]["id"]


async def test_generate_and_pay_invoice_rolls_subscription_period_forward(
    client: AsyncClient, lite_tenant: dict, product_owner: User
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    headers = auth_headers(owner_tokens["access_token"])
    subscription_id = await _get_subscription_id(client, headers, str(lite_tenant["tenant"].id))

    before = await client.get(
        "/api/v1/platform/subscriptions",
        params={"tenant_id": str(lite_tenant["tenant"].id)},
        headers=headers,
    )
    period_end_before = before.json()["items"][0]["current_period_end"]

    generate_resp = await client.post(
        "/api/v1/platform/invoices/generate",
        json={"subscription_id": subscription_id},
        headers=headers,
    )
    assert generate_resp.status_code == 201, generate_resp.text
    invoice = generate_resp.json()
    assert invoice["status"] == "pending"
    assert invoice["amount_paise"] == 79_900
    assert invoice["gst_paise"] == 14_382  # 18% of 79,900

    pay_resp = await client.patch(
        f"/api/v1/platform/invoices/{invoice['id']}",
        json={"status": "paid"},
        headers=headers,
    )
    assert pay_resp.status_code == 200
    assert pay_resp.json()["status"] == "paid"
    assert pay_resp.json()["paid_at"] is not None

    after = await client.get(
        "/api/v1/platform/subscriptions",
        params={"tenant_id": str(lite_tenant["tenant"].id)},
        headers=headers,
    )
    period_end_after = after.json()["items"][0]["current_period_end"]
    assert period_end_after != period_end_before
    assert after.json()["items"][0]["status"] == "active"


async def test_mark_invoice_failed_sets_subscription_past_due(
    client: AsyncClient, lite_tenant: dict, product_owner: User
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    headers = auth_headers(owner_tokens["access_token"])
    subscription_id = await _get_subscription_id(client, headers, str(lite_tenant["tenant"].id))

    generate_resp = await client.post(
        "/api/v1/platform/invoices/generate",
        json={"subscription_id": subscription_id},
        headers=headers,
    )
    invoice_id = generate_resp.json()["id"]

    fail_resp = await client.patch(
        f"/api/v1/platform/invoices/{invoice_id}",
        json={"status": "failed"},
        headers=headers,
    )
    assert fail_resp.status_code == 200
    assert fail_resp.json()["status"] == "failed"

    subs_resp = await client.get(
        "/api/v1/platform/subscriptions",
        params={"tenant_id": str(lite_tenant["tenant"].id)},
        headers=headers,
    )
    assert subs_resp.json()["items"][0]["status"] == "past_due"


async def test_invoices_require_product_owner(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        "/api/v1/platform/invoices", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 403
