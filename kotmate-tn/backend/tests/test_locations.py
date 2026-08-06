import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _location_payload(**overrides) -> dict:
    payload = {
        "name": "Branch Two",
        "door_no": "2",
        "street": "Second Street",
        "city": "Coimbatore",
        "district": "Coimbatore",
        "state": "Tamil Nadu",
        "pincode": "641001",
    }
    payload.update(overrides)
    return payload


async def _pro_tenant_admin(client: AsyncClient, owner_headers: dict) -> dict:
    suffix = uuid.uuid4().hex[:6]
    payload = {
        "company_name": f"Pro Hotel {suffix}",
        "door_no": "1",
        "street": "Main Street",
        "city": "Chennai",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "pincode": "600001",
        "plan_code": "pro",
        "billing_cycle": "monthly",
        "location_name": f"Pro Hotel {suffix} - Main",
        "admin_local_handle": "admin01",
        "admin_name": "Pro Admin",
        "admin_password": "password123",
    }
    resp = await client.post("/api/v1/platform/tenants", json=payload, headers=owner_headers)
    assert resp.status_code == 201, resp.text
    tenant = resp.json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": tenant["admin_login_id"], "password": "password123"}
    )
    assert login.status_code == 200
    return {"tenant": tenant, "headers": {"Authorization": f"Bearer {login.json()['access_token']}"}}


async def test_lite_tenant_blocked_from_second_location(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    resp = await client.post("/api/v1/locations", json=_location_payload(), headers=headers)
    assert resp.status_code == 403
    assert "upgrade" in resp.json()["detail"].lower()


async def test_pro_tenant_allows_second_but_not_third_location(
    client: AsyncClient, owner_headers: dict
):
    pro = await _pro_tenant_admin(client, owner_headers)
    headers = pro["headers"]

    second = await client.post("/api/v1/locations", json=_location_payload(), headers=headers)
    assert second.status_code == 201, second.text

    third = await client.post(
        "/api/v1/locations", json=_location_payload(name="Branch Three"), headers=headers
    )
    assert third.status_code == 403


async def test_pro_max_tenant_allows_up_to_five_locations(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    # Tenant already has 1 (seeded at onboarding) — 4 more should succeed, the 6th fails.
    for i in range(4):
        resp = await client.post(
            "/api/v1/locations", json=_location_payload(name=f"Branch {i + 2}"), headers=headers
        )
        assert resp.status_code == 201, resp.text

    over_cap = await client.post(
        "/api/v1/locations", json=_location_payload(name="Branch Six"), headers=headers
    )
    assert over_cap.status_code == 403


async def test_manage_endpoint_shows_inactive_locations(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    created = (
        await client.post("/api/v1/locations", json=_location_payload(), headers=headers)
    ).json()

    deactivate = await client.patch(
        f"/api/v1/locations/{created['id']}", json={"is_active": False}, headers=headers
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    # Deactivated location drops out of the broad picker...
    picker = (await client.get("/api/v1/locations", headers=headers)).json()
    assert not any(loc["id"] == created["id"] for loc in picker)

    # ...but stays visible (with its full detail) in the admin "manage" view.
    manage = (await client.get("/api/v1/locations/manage", headers=headers)).json()
    managed = next(loc for loc in manage if loc["id"] == created["id"])
    assert managed["is_active"] is False
    assert managed["city"] == "Coimbatore"


async def test_reactivating_location_still_subject_to_cap(client: AsyncClient, owner_headers: dict):
    pro = await _pro_tenant_admin(client, owner_headers)
    headers = pro["headers"]

    second = (
        await client.post("/api/v1/locations", json=_location_payload(), headers=headers)
    ).json()
    await client.patch(f"/api/v1/locations/{second['id']}", json={"is_active": False}, headers=headers)

    # Back under cap (1 active) — a fresh 2nd location can be created again.
    third = await client.post(
        "/api/v1/locations", json=_location_payload(name="Branch Three"), headers=headers
    )
    assert third.status_code == 201

    # Now at cap (2 active) — reactivating the deactivated one should be blocked.
    reactivate = await client.patch(
        f"/api/v1/locations/{second['id']}", json={"is_active": True}, headers=headers
    )
    assert reactivate.status_code == 403


async def test_non_tenant_admin_can_read_but_not_write_locations(client: AsyncClient, tenant_admin: dict):
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

    assert (await client.get("/api/v1/locations", headers=waiter_headers)).status_code == 200
    assert (await client.get("/api/v1/locations/manage", headers=waiter_headers)).status_code == 403
    create_resp = await client.post(
        "/api/v1/locations", json=_location_payload(), headers=waiter_headers
    )
    assert create_resp.status_code == 403
