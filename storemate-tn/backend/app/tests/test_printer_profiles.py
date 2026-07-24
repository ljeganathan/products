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
