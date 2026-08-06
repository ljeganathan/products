import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import _login

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_cashier_with_incentive_rate_and_login(client: AsyncClient, tenant_admin: dict):
    resp = await client.post(
        "/api/v1/users",
        json={
            "local_handle": "cashier01",
            "name": "Cashier One",
            "role": "pos_user",
            "password": "password123",
            "incentive_rate": 2.5,
        },
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == f"{tenant_admin['tenant']['tenant_code']}-cashier01"
    assert body["local_handle"] == "cashier01"
    assert body["incentive_rate"] == 2.5
    assert body["role"] == "pos_user"

    login_headers = await _login(client, body["user_id"])
    assert login_headers is not None


async def test_incentive_rate_rejected_for_non_cashier_role(client: AsyncClient, tenant_admin: dict):
    resp = await client.post(
        "/api/v1/users",
        json={
            "local_handle": "waiter01",
            "name": "Waiter One",
            "role": "waiter",
            "password": "password123",
            "incentive_rate": 3.0,
        },
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 422


async def test_lite_tier_blocks_third_billable_user(client: AsyncClient, tenant_admin: dict):
    # Lite = max_users 2. The tenant already has 1 billable seat (its tenant_admin).
    first = await client.post(
        "/api/v1/users",
        json={"local_handle": "cashier01", "name": "C1", "role": "pos_user", "password": "password123"},
        headers=tenant_admin["headers"],
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/users",
        json={"local_handle": "cashier02", "name": "C2", "role": "pos_user", "password": "password123"},
        headers=tenant_admin["headers"],
    )
    assert second.status_code == 409
    assert "seat limit" in second.json()["detail"].lower()

    # Waiter/kitchen seats are uncapped even on Lite.
    waiter_resp = await client.post(
        "/api/v1/users",
        json={"local_handle": "waiter01", "name": "W1", "role": "waiter", "password": "password123"},
        headers=tenant_admin["headers"],
    )
    assert waiter_resp.status_code == 201


async def test_pro_max_tenant_has_unlimited_billable_seats(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    for i in range(4):
        resp = await client.post(
            "/api/v1/users",
            json={
                "local_handle": f"cashier{i}",
                "name": f"C{i}",
                "role": "pos_user",
                "password": "password123",
            },
            headers=pro_max_tenant_admin["headers"],
        )
        assert resp.status_code == 201


async def test_deactivated_user_cannot_login(client: AsyncClient, tenant_admin: dict):
    create_resp = await client.post(
        "/api/v1/users",
        json={"local_handle": "kot01", "name": "Kitchen One", "role": "kitchen", "password": "password123"},
        headers=tenant_admin["headers"],
    )
    assert create_resp.status_code == 201
    user = create_resp.json()

    login_ok = await client.post(
        "/api/v1/auth/login", json={"user_id": user["user_id"], "password": "password123"}
    )
    assert login_ok.status_code == 200

    deactivate_resp = await client.patch(
        f"/api/v1/users/{user['id']}", json={"is_active": False}, headers=tenant_admin["headers"]
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    login_blocked = await client.post(
        "/api/v1/auth/login", json={"user_id": user["user_id"], "password": "password123"}
    )
    assert login_blocked.status_code == 401


async def test_reactivating_billable_user_respects_seat_cap(client: AsyncClient, tenant_admin: dict):
    # Fill the Lite seat cap (admin + 1 cashier = 2), deactivate the cashier, add a
    # second cashier to refill the freed seat, then reactivating the first must 409.
    cashier1 = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "c1", "name": "C1", "role": "pos_user", "password": "password123"},
            headers=tenant_admin["headers"],
        )
    ).json()
    await client.patch(
        f"/api/v1/users/{cashier1['id']}", json={"is_active": False}, headers=tenant_admin["headers"]
    )
    cashier2 = await client.post(
        "/api/v1/users",
        json={"local_handle": "c2", "name": "C2", "role": "pos_user", "password": "password123"},
        headers=tenant_admin["headers"],
    )
    assert cashier2.status_code == 201

    reactivate = await client.patch(
        f"/api/v1/users/{cashier1['id']}", json={"is_active": True}, headers=tenant_admin["headers"]
    )
    assert reactivate.status_code == 409


async def test_password_reset(client: AsyncClient, tenant_admin: dict):
    create_resp = await client.post(
        "/api/v1/users",
        json={"local_handle": "w1", "name": "W1", "role": "waiter", "password": "oldpassword1"},
        headers=tenant_admin["headers"],
    )
    user = create_resp.json()

    reset_resp = await client.post(
        f"/api/v1/users/{user['id']}/reset-password",
        json={"new_password": "newpassword1"},
        headers=tenant_admin["headers"],
    )
    assert reset_resp.status_code == 204

    old_login = await client.post(
        "/api/v1/auth/login", json={"user_id": user["user_id"], "password": "oldpassword1"}
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login", json={"user_id": user["user_id"], "password": "newpassword1"}
    )
    assert new_login.status_code == 200


async def test_location_access_assignment(client: AsyncClient, tenant_admin: dict):
    locations_resp = await client.get("/api/v1/locations", headers=tenant_admin["headers"])
    assert locations_resp.status_code == 200
    locations = locations_resp.json()
    assert len(locations) == 1
    location_id = locations[0]["id"]

    create_resp = await client.post(
        "/api/v1/users",
        json={
            "local_handle": "w2",
            "name": "W2",
            "role": "waiter",
            "password": "password123",
            "location_ids": [location_id],
        },
        headers=tenant_admin["headers"],
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["location_ids"] == [location_id]

    bad_resp = await client.post(
        "/api/v1/users",
        json={
            "local_handle": "w3",
            "name": "W3",
            "role": "waiter",
            "password": "password123",
            "location_ids": [str(uuid.uuid4())],
        },
        headers=tenant_admin["headers"],
    )
    assert bad_resp.status_code == 400


async def test_seat_usage_endpoint_reflects_counts(client: AsyncClient, tenant_admin: dict):
    before = await client.get("/api/v1/users/seat-usage", headers=tenant_admin["headers"])
    assert before.json() == {"active_billable_users": 1, "max_users": 2}

    await client.post(
        "/api/v1/users",
        json={"local_handle": "c1", "name": "C1", "role": "pos_user", "password": "password123"},
        headers=tenant_admin["headers"],
    )
    after = await client.get("/api/v1/users/seat-usage", headers=tenant_admin["headers"])
    assert after.json() == {"active_billable_users": 2, "max_users": 2}


async def test_non_tenant_admin_blocked_from_user_management(client: AsyncClient, tenant_admin: dict):
    cashier = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "c1", "name": "C1", "role": "pos_user", "password": "password123"},
            headers=tenant_admin["headers"],
        )
    ).json()
    cashier_headers = await _login(client, cashier["user_id"])

    resp = await client.get("/api/v1/users", headers=cashier_headers)
    assert resp.status_code == 403


async def test_kot_user_role_composed_correctly(client: AsyncClient, tenant_admin: dict):
    resp = await client.post(
        "/api/v1/users",
        json={"local_handle": "kot01", "name": "Kitchen One", "role": "kitchen", "password": "password123"},
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "kitchen"

    login_resp = await client.post(
        "/api/v1/auth/login", json={"user_id": body["user_id"], "password": "password123"}
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["role"] == "kitchen"
