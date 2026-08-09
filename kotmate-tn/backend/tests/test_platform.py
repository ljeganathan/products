import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import async_session_maker
from app.models import Role, User
from tests.conftest import _set_platform_admin, _tenant_payload

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_non_product_owner_blocked_from_platform_routes(client: AsyncClient):
    async with async_session_maker() as session:
        await _set_platform_admin(session)
        role = (await session.execute(select(Role).where(Role.code == "tenant_admin"))).scalar_one()
        login_id = f"notowner-{uuid.uuid4().hex[:8]}"
        session.add(
            User(
                tenant_id=None,
                user_id=login_id,
                password_hash=hash_password("password123"),
                role_id=role.id,
                name=login_id,
                is_active=True,
            )
        )
        await session.commit()

    login_resp = await client.post(
        "/api/v1/auth/login", json={"user_id": login_id, "password": "password123"}
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    resp = await client.get("/api/v1/platform/tenants", headers=headers)
    assert resp.status_code == 403


async def test_create_tenant_end_to_end_and_login_as_admin(client: AsyncClient, owner_headers: dict):
    payload = _tenant_payload()
    create_resp = await client.post("/api/v1/platform/tenants", json=payload, headers=owner_headers)
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["plan_code"] == "lite"
    assert body["active_user_count"] == 1
    assert body["active_location_count"] == 1
    assert body["admin_login_id"] == f"{body['tenant_code']}admin01"

    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"user_id": body["admin_login_id"], "password": payload["admin_password"]},
    )
    assert admin_login.status_code == 200
    admin_body = admin_login.json()
    assert admin_body["role"] == "tenant_admin"
    assert admin_body["tenant_id"] == body["id"]


async def test_tenant_code_collision_gets_a_distinct_suffix(client: AsyncClient, owner_headers: dict):
    # Two tenants with the same company-name initials (and the same admin local handle)
    # must not collide on the composed login id — generate_tenant_code suffixes the
    # second one, so both onboard successfully with distinct tenant_code/login ids.
    payload = _tenant_payload(company_name="Zzq Unique Corp", admin_local_handle="admin01")
    first = await client.post("/api/v1/platform/tenants", json=payload, headers=owner_headers)
    assert first.status_code == 201

    payload_2 = _tenant_payload(company_name="Zzq Unique Corp", admin_local_handle="admin01")
    second = await client.post("/api/v1/platform/tenants", json=payload_2, headers=owner_headers)
    assert second.status_code == 201
    assert first.json()["tenant_code"] != second.json()["tenant_code"]
    assert first.json()["admin_login_id"] != second.json()["admin_login_id"]


async def test_plan_change_reflected_in_me_features(client: AsyncClient, owner_headers: dict):
    create_resp = await client.post(
        "/api/v1/platform/tenants", json=_tenant_payload(), headers=owner_headers
    )
    tenant = create_resp.json()

    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"user_id": tenant["admin_login_id"], "password": "password123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    me_before = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert me_before.json()["plan_code"] == "lite"
    assert me_before.json()["max_locations"] == 1

    change_resp = await client.post(
        f"/api/v1/platform/tenants/{tenant['id']}/change-plan",
        json={"plan_code": "pro_max", "billing_cycle": "monthly"},
        headers=owner_headers,
    )
    assert change_resp.status_code == 200
    assert change_resp.json()["plan_code"] == "pro_max"

    me_after = await client.get("/api/v1/auth/me", headers=admin_headers)
    body = me_after.json()
    assert body["plan_code"] == "pro_max"
    assert body["max_locations"] == 5
    assert body["max_users"] is None  # Pro Max = unlimited


async def test_maintenance_mode_blocks_non_owner_login(client: AsyncClient, owner_headers: dict):
    create_resp = await client.post(
        "/api/v1/platform/tenants", json=_tenant_payload(), headers=owner_headers
    )
    tenant = create_resp.json()

    toggle_on = await client.patch(
        "/api/v1/platform/maintenance",
        json={"maintenance_mode": True, "maintenance_message": "Down for upgrades, back soon."},
        headers=owner_headers,
    )
    assert toggle_on.status_code == 200

    try:
        blocked = await client.post(
            "/api/v1/auth/login",
            json={"user_id": tenant["admin_login_id"], "password": "password123"},
        )
        assert blocked.status_code == 503
        assert "upgrades" in blocked.json()["detail"]

        # product_owner is exempt.
        owner_retry = await client.get("/api/v1/platform/tenants", headers=owner_headers)
        assert owner_retry.status_code == 200
    finally:
        await client.patch(
            "/api/v1/platform/maintenance", json={"maintenance_mode": False}, headers=owner_headers
        )


async def test_plans_list_and_update(client: AsyncClient, owner_headers: dict):
    list_resp = await client.get("/api/v1/platform/plans", headers=owner_headers)
    assert list_resp.status_code == 200
    plans = list_resp.json()
    assert {p["code"] for p in plans} == {"lite", "pro", "pro_max"}

    # Phase 21 product decision: Pro tenants get Item Master CSV import too now, not
    # just export — locks in the data migration (9c46b3480166) that flipped this.
    pro = next(p for p in plans if p["code"] == "pro")
    assert pro["features"]["item_import"] is True

    lite = next(p for p in plans if p["code"] == "lite")
    update_resp = await client.patch(
        f"/api/v1/platform/plans/{lite['id']}",
        json={"price_monthly": 1099.0},
        headers=owner_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["price_monthly"] == 1099.0

    # Restore, since plans are shared seed data other tests read.
    await client.patch(
        f"/api/v1/platform/plans/{lite['id']}",
        json={"price_monthly": float(lite["price_monthly"])},
        headers=owner_headers,
    )


async def test_metrics_endpoint_returns_sane_shape(client: AsyncClient, owner_headers: dict):
    resp = await client.get("/api/v1/platform/metrics", headers=owner_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_tenant_count"] >= 0
    assert body["mrr_estimate"] >= 0
    assert body["total_active_locations"] >= 0
