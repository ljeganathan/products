import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _default_location_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/api/v1/locations", headers=headers)
    return resp.json()[0]["id"]


async def test_create_and_list_printer(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)

    resp = await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Counter Bill Printer",
            "target": "bill",
            "printer_type": "thermal",
            "connection_type": "usb",
            "connection_details": {"vendor_id": "0x04b8"},
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["target"] == "bill"
    assert body["is_active"] is True

    list_resp = await client.get("/api/v1/printers", headers=headers)
    assert list_resp.status_code == 200
    assert any(p["id"] == body["id"] for p in list_resp.json())


async def test_printer_location_must_belong_to_tenant(client: AsyncClient, tenant_admin: dict):
    resp = await client.post(
        "/api/v1/printers",
        json={
            "location_id": "00000000-0000-0000-0000-000000000000",
            "name": "Ghost Printer",
            "target": "kot",
            "printer_type": "thermal",
            "connection_type": "network",
        },
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 400


async def test_invalid_printer_type_rejected(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    resp = await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Bad Printer",
            "target": "kot",
            "printer_type": "laser",
            "connection_type": "network",
        },
        headers=headers,
    )
    assert resp.status_code == 422


async def test_update_printer_deactivate(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    create_resp = await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Kitchen Printer",
            "target": "kot",
            "printer_type": "dotmatrix",
            "connection_type": "local_agent",
        },
        headers=headers,
    )
    printer = create_resp.json()

    update_resp = await client.patch(
        f"/api/v1/printers/{printer['id']}", json={"is_active": False}, headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False


async def test_non_tenant_admin_can_read_but_not_write_printers(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
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

    list_resp = await client.get("/api/v1/printers", headers=waiter_headers)
    assert list_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Blocked",
            "target": "kot",
            "printer_type": "thermal",
            "connection_type": "network",
        },
        headers=waiter_headers,
    )
    assert create_resp.status_code == 403
