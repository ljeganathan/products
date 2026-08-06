import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _default_location_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/api/v1/locations", headers=headers)
    return resp.json()[0]["id"]


async def _section_id(client: AsyncClient, headers: dict, name_en: str) -> str:
    resp = await client.get("/api/v1/sections", headers=headers)
    return next(s["id"] for s in resp.json() if s["name_en"] == name_en)


async def test_create_table_with_seating_section(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    ac_section_id = await _section_id(client, headers, "AC")

    resp = await client.post(
        "/api/v1/tables",
        json={
            "location_id": location_id,
            "section_id": ac_section_id,
            "table_number": "T1",
            "seating_capacity": 4,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["table_number"] == "T1"
    assert body["status"] == "free"
    assert body["is_active"] is True


async def test_non_seating_section_rejected_for_table(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    takeaway_section_id = await _section_id(client, headers, "Takeaway")

    resp = await client.post(
        "/api/v1/tables",
        json={"location_id": location_id, "section_id": takeaway_section_id, "table_number": "T2"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "non-seating" in resp.json()["detail"].lower()


async def test_table_number_unique_per_location(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    ac_section_id = await _section_id(client, headers, "AC")

    first = await client.post(
        "/api/v1/tables",
        json={"location_id": location_id, "section_id": ac_section_id, "table_number": "T3"},
        headers=headers,
    )
    assert first.status_code == 201

    dup = await client.post(
        "/api/v1/tables",
        json={"location_id": location_id, "section_id": ac_section_id, "table_number": "T3"},
        headers=headers,
    )
    assert dup.status_code == 409


async def test_section_id_must_belong_to_tenant(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)

    resp = await client.post(
        "/api/v1/tables",
        json={
            "location_id": location_id,
            "section_id": "00000000-0000-0000-0000-000000000000",
            "table_number": "T4",
        },
        headers=headers,
    )
    assert resp.status_code == 400


async def test_soft_deactivate_table(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    ac_section_id = await _section_id(client, headers, "AC")

    create_resp = await client.post(
        "/api/v1/tables",
        json={"location_id": location_id, "section_id": ac_section_id, "table_number": "T5"},
        headers=headers,
    )
    table = create_resp.json()

    deactivate_resp = await client.patch(
        f"/api/v1/tables/{table['id']}", json={"is_active": False}, headers=headers
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    list_resp = await client.get("/api/v1/tables", headers=headers)
    assert any(t["id"] == table["id"] and not t["is_active"] for t in list_resp.json())


async def test_updating_table_to_non_seating_section_rejected(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    ac_section_id = await _section_id(client, headers, "AC")
    takeaway_section_id = await _section_id(client, headers, "Takeaway")

    table = (
        await client.post(
            "/api/v1/tables",
            json={"location_id": location_id, "section_id": ac_section_id, "table_number": "T6"},
            headers=headers,
        )
    ).json()

    resp = await client.patch(
        f"/api/v1/tables/{table['id']}", json={"section_id": takeaway_section_id}, headers=headers
    )
    assert resp.status_code == 400


async def test_non_tenant_admin_can_read_but_not_write_tables(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    waiter_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w1", "name": "W1", "role": "waiter", "password": "password123"},
            headers=headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter_user["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    list_resp = await client.get("/api/v1/tables", headers=waiter_headers)
    assert list_resp.status_code == 200

    location_id = await _default_location_id(client, headers)
    ac_section_id = await _section_id(client, headers, "AC")
    create_resp = await client.post(
        "/api/v1/tables",
        json={"location_id": location_id, "section_id": ac_section_id, "table_number": "T7"},
        headers=waiter_headers,
    )
    assert create_resp.status_code == 403
