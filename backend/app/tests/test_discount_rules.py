from httpx import AsyncClient

from app.tests.conftest import auth_headers, login


async def test_discount_rules_blocked_on_lite_plan(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        "/api/v1/discount-rules", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 403
    assert "upgrade" in resp.json()["detail"].lower()


async def test_create_bill_scope_rule_on_pro_plan(client: AsyncClient, pro_tenant: dict) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    resp = await client.post(
        "/api/v1/discount-rules",
        json={"scope": "bill", "type": "percent", "value": 500},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["scope"] == "bill"
    assert body["target_id"] is None


async def test_item_scope_rule_requires_target_id(client: AsyncClient, pro_tenant: dict) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    resp = await client.post(
        "/api/v1/discount-rules",
        json={"scope": "item", "type": "flat", "value": 1000},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_bill_scope_rule_rejects_target_id(client: AsyncClient, pro_tenant: dict) -> None:
    import uuid

    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    resp = await client.post(
        "/api/v1/discount-rules",
        json={"scope": "bill", "type": "flat", "value": 1000, "target_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_update_and_delete_discount_rule(client: AsyncClient, pro_tenant: dict) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    create_resp = await client.post(
        "/api/v1/discount-rules",
        json={"scope": "bill", "type": "percent", "value": 500, "is_active": True},
        headers=headers,
    )
    rule_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/discount-rules/{rule_id}", json={"is_active": False}, headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False

    list_resp = await client.get(
        "/api/v1/discount-rules", params={"is_active": False}, headers=headers
    )
    assert list_resp.json()["total"] == 1

    delete_resp = await client.delete(f"/api/v1/discount-rules/{rule_id}", headers=headers)
    assert delete_resp.status_code == 204

    list_after = await client.get("/api/v1/discount-rules", headers=headers)
    assert list_after.json()["total"] == 0
