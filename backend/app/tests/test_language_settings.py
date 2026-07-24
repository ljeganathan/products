from httpx import AsyncClient

from app.tests.conftest import auth_headers, login


async def test_get_and_update_language_settings(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    get_resp = await client.get("/api/v1/settings/language", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["language_pref"] == "en"

    update_resp = await client.patch(
        "/api/v1/settings/language", json={"language_pref": "ta"}, headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["language_pref"] == "ta"

    get_after = await client.get("/api/v1/settings/language", headers=headers)
    assert get_after.json()["language_pref"] == "ta"
