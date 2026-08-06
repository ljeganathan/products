import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _default_location_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/api/v1/locations", headers=headers)
    assert resp.status_code == 200
    return resp.json()[0]["id"]


async def test_create_waiter_and_list(client: AsyncClient, tenant_admin: dict):
    location_id = await _default_location_id(client, tenant_admin["headers"])
    resp = await client.post(
        "/api/v1/waiters",
        json={"location_id": location_id, "waiter_number": "W1", "name": "Ravi", "incentive_rate": 1.5},
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["waiter_number"] == "W1"
    assert body["incentive_rate"] == 1.5
    assert body["is_active"] is True

    list_resp = await client.get("/api/v1/waiters", headers=tenant_admin["headers"])
    assert list_resp.status_code == 200
    assert any(w["id"] == body["id"] for w in list_resp.json())


async def test_waiter_number_unique_per_location(client: AsyncClient, tenant_admin: dict):
    location_id = await _default_location_id(client, tenant_admin["headers"])
    first = await client.post(
        "/api/v1/waiters",
        json={"location_id": location_id, "waiter_number": "W2", "name": "Kumar"},
        headers=tenant_admin["headers"],
    )
    assert first.status_code == 201

    dup = await client.post(
        "/api/v1/waiters",
        json={"location_id": location_id, "waiter_number": "W2", "name": "Someone Else"},
        headers=tenant_admin["headers"],
    )
    assert dup.status_code == 409
    assert "waiter number" in dup.json()["detail"].lower()


async def test_location_id_must_belong_to_tenant(client: AsyncClient, tenant_admin: dict):
    resp = await client.post(
        "/api/v1/waiters",
        json={
            "location_id": "00000000-0000-0000-0000-000000000000",
            "waiter_number": "W3",
            "name": "Ghost",
        },
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 400


async def test_soft_deactivate_waiter(client: AsyncClient, tenant_admin: dict):
    location_id = await _default_location_id(client, tenant_admin["headers"])
    create_resp = await client.post(
        "/api/v1/waiters",
        json={"location_id": location_id, "waiter_number": "W4", "name": "Mani"},
        headers=tenant_admin["headers"],
    )
    waiter = create_resp.json()

    deactivate_resp = await client.patch(
        f"/api/v1/waiters/{waiter['id']}", json={"is_active": False}, headers=tenant_admin["headers"]
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    # Still readable — soft-deactivate, not hard delete.
    list_resp = await client.get("/api/v1/waiters", headers=tenant_admin["headers"])
    assert any(w["id"] == waiter["id"] and not w["is_active"] for w in list_resp.json())


async def test_incentive_rate_out_of_range_rejected(client: AsyncClient, tenant_admin: dict):
    location_id = await _default_location_id(client, tenant_admin["headers"])
    resp = await client.post(
        "/api/v1/waiters",
        json={
            "location_id": location_id,
            "waiter_number": "W5",
            "name": "Bad Rate",
            "incentive_rate": 150,
        },
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 422


async def test_non_tenant_admin_can_read_but_not_write_waiters(client: AsyncClient, tenant_admin: dict):
    waiter_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w1", "name": "W1", "role": "waiter", "password": "password123"},
            headers=tenant_admin["headers"],
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter_user["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    list_resp = await client.get("/api/v1/waiters", headers=waiter_headers)
    assert list_resp.status_code == 200

    location_id = await _default_location_id(client, tenant_admin["headers"])
    create_resp = await client.post(
        "/api/v1/waiters",
        json={"location_id": location_id, "waiter_number": "W6", "name": "Blocked"},
        headers=waiter_headers,
    )
    assert create_resp.status_code == 403


async def test_link_waiter_to_login_and_resolve_via_me(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    waiter_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w7", "name": "W7", "role": "waiter", "password": "password123"},
            headers=headers,
        )
    ).json()

    waiter = await client.post(
        "/api/v1/waiters",
        json={
            "location_id": location_id,
            "waiter_number": "W7",
            "name": "W7",
            "user_id": waiter_user["id"],
        },
        headers=headers,
    )
    assert waiter.status_code == 201
    assert waiter.json()["user_id"] == waiter_user["id"]

    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter_user["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me_resp = await client.get("/api/v1/waiters/me", headers=waiter_headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == waiter.json()["id"]


async def test_user_id_must_be_waiter_role_login(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    cashier = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "c1", "name": "C1", "role": "pos_user", "password": "password123"},
            headers=headers,
        )
    ).json()

    resp = await client.post(
        "/api/v1/waiters",
        json={
            "location_id": location_id,
            "waiter_number": "W8",
            "name": "W8",
            "user_id": cashier["id"],
        },
        headers=headers,
    )
    assert resp.status_code == 400


async def test_user_id_cannot_be_linked_to_two_waiters(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    waiter_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w9", "name": "W9", "role": "waiter", "password": "password123"},
            headers=headers,
        )
    ).json()
    first = await client.post(
        "/api/v1/waiters",
        json={
            "location_id": location_id,
            "waiter_number": "W9a",
            "name": "W9a",
            "user_id": waiter_user["id"],
        },
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/waiters",
        json={
            "location_id": location_id,
            "waiter_number": "W9b",
            "name": "W9b",
            "user_id": waiter_user["id"],
        },
        headers=headers,
    )
    assert second.status_code == 409


async def test_waiter_me_returns_null_when_unlinked(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    waiter_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w10", "name": "W10", "role": "waiter", "password": "password123"},
            headers=headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter_user["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    me_resp = await client.get("/api/v1/waiters/me", headers=waiter_headers)
    assert me_resp.status_code == 200
    assert me_resp.json() is None
