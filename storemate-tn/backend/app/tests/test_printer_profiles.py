import base64
import socket
import threading

from httpx import AsyncClient

from app.tests.conftest import auth_headers, login


async def test_create_printer_profile_happy_path(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter 1",
            "type": "thermal_80mm",
            "connection": "webusb",
            "paper_width_chars": 42,
            "is_default": True,
        },
        headers=auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_default"] is True


async def test_printer_profile_limit_enforced_on_lite_plan(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    first = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter 1",
            "type": "thermal_58mm",
            "connection": "webusb",
            "paper_width_chars": 32,
        },
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter 2",
            "type": "thermal_58mm",
            "connection": "webusb",
            "paper_width_chars": 32,
        },
        headers=headers,
    )
    assert second.status_code == 402


async def test_setting_new_default_unsets_previous_default(
    client: AsyncClient, pro_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    first = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter 1",
            "type": "thermal_58mm",
            "connection": "webusb",
            "paper_width_chars": 32,
            "is_default": True,
        },
        headers=headers,
    )
    first_id = first.json()["id"]

    second = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter 2",
            "type": "thermal_80mm",
            "connection": "local_agent",
            "paper_width_chars": 42,
            "is_default": True,
        },
        headers=headers,
    )
    assert second.json()["is_default"] is True

    listing = await client.get("/api/v1/settings/printer-profiles", headers=headers)
    first_after = next(p for p in listing.json() if p["id"] == first_id)
    assert first_after["is_default"] is False


async def test_create_printer_profile_with_connection_details(
    client: AsyncClient, pro_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    resp = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter (WiFi)",
            "type": "thermal_80mm",
            "connection": "network",
            "paper_width_chars": 42,
            "connection_details": {"ip": "192.168.1.50", "port": "9100"},
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["connection_details"] == {"ip": "192.168.1.50", "port": "9100"}

    bluetooth_resp = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter (BT)",
            "type": "thermal_58mm",
            "connection": "bluetooth",
            "paper_width_chars": 32,
            "connection_details": {
                "bluetooth_device_id": "abc123",
                "bluetooth_device_name": "Posiflow KP307",
            },
        },
        headers=headers,
    )
    assert bluetooth_resp.status_code == 201, bluetooth_resp.text

    rawbt_resp = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Tablet (RawBT)",
            "type": "thermal_58mm",
            "connection": "rawbt",
            "paper_width_chars": 32,
        },
        headers=headers,
    )
    assert rawbt_resp.status_code == 201, rawbt_resp.text
    assert rawbt_resp.json()["connection_details"] == {}


async def test_print_network_accepts_wifi_connection_type(
    client: AsyncClient, pro_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server_port = server.getsockname()[1]

    def accept_once() -> None:
        conn, _ = server.accept()
        conn.close()

    thread = threading.Thread(target=accept_once, daemon=True)
    thread.start()

    created = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter (WiFi)",
            "type": "thermal_58mm",
            "connection": "wifi",
            "paper_width_chars": 32,
            "connection_details": {"ip": "127.0.0.1", "port": str(server_port)},
        },
        headers=headers,
    )
    profile_id = created.json()["id"]

    resp = await client.post(
        f"/api/v1/settings/printer-profiles/{profile_id}/print-network",
        json={"data_base64": base64.b64encode(b"hi").decode()},
        headers=headers,
    )
    assert resp.status_code == 204, resp.text
    thread.join(timeout=2)
    server.close()


async def test_print_network_rejects_non_network_profile(
    client: AsyncClient, pro_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    created = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter 1",
            "type": "thermal_58mm",
            "connection": "webusb",
            "paper_width_chars": 32,
        },
        headers=headers,
    )
    profile_id = created.json()["id"]

    resp = await client.post(
        f"/api/v1/settings/printer-profiles/{profile_id}/print-network",
        json={"data_base64": base64.b64encode(b"hello").decode()},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_print_network_success_and_unreachable(client: AsyncClient, pro_tenant: dict) -> None:
    tokens = await login(client, "admin@tenantpro.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    received: list[bytes] = []
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    server_port = server.getsockname()[1]

    def accept_once() -> None:
        conn, _ = server.accept()
        with conn:
            received.append(conn.recv(4096))

    thread = threading.Thread(target=accept_once, daemon=True)
    thread.start()

    created = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter (WiFi)",
            "type": "thermal_80mm",
            "connection": "network",
            "paper_width_chars": 42,
            "connection_details": {"ip": "127.0.0.1", "port": str(server_port)},
        },
        headers=headers,
    )
    profile_id = created.json()["id"]

    resp = await client.post(
        f"/api/v1/settings/printer-profiles/{profile_id}/print-network",
        json={"data_base64": base64.b64encode(b"hello printer").decode()},
        headers=headers,
    )
    assert resp.status_code == 204, resp.text
    thread.join(timeout=2)
    server.close()
    assert received == [b"hello printer"]

    unreachable = await client.post(
        "/api/v1/settings/printer-profiles",
        json={
            "name": "Counter (unreachable)",
            "type": "thermal_80mm",
            "connection": "network",
            "paper_width_chars": 42,
            "connection_details": {"ip": "127.0.0.1", "port": "1"},
        },
        headers=headers,
    )
    unreachable_id = unreachable.json()["id"]
    fail_resp = await client.post(
        f"/api/v1/settings/printer-profiles/{unreachable_id}/print-network",
        json={"data_base64": base64.b64encode(b"hello").decode()},
        headers=headers,
    )
    assert fail_resp.status_code == 502
