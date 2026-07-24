from httpx import AsyncClient

from app.models.user import User
from app.tests.conftest import auth_headers, login


async def test_maintenance_settings_requires_product_owner(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        "/api/v1/platform/settings", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 403


async def test_maintenance_toggle_round_trip_and_banner_visible_to_tenant_users(
    client: AsyncClient, lite_tenant: dict, product_owner: User
) -> None:
    owner_tokens = await login(client, "owner@storematetn.dev", "Owner@123")
    owner_headers = auth_headers(owner_tokens["access_token"])

    off = await client.get("/api/v1/platform/maintenance-status", headers=owner_headers)
    assert off.status_code == 200
    assert off.json()["maintenance_mode"] is False

    patch_resp = await client.patch(
        "/api/v1/platform/settings",
        json={
            "maintenance_mode": True,
            "maintenance_message": "Upgrading servers, back in 30 min.",
        },
        headers=owner_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["maintenance_mode"] is True

    # A tenant admin (any authenticated role, not just product_owner) sees it too.
    admin_tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    status_resp = await client.get(
        "/api/v1/platform/maintenance-status", headers=auth_headers(admin_tokens["access_token"])
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["maintenance_mode"] is True
    assert "back in 30 min" in status_resp.json()["maintenance_message"]

    # Turn it back off and confirm the flag clears for everyone.
    await client.patch(
        "/api/v1/platform/settings", json={"maintenance_mode": False}, headers=owner_headers
    )
    final = await client.get(
        "/api/v1/platform/maintenance-status", headers=auth_headers(admin_tokens["access_token"])
    )
    assert final.json()["maintenance_mode"] is False
