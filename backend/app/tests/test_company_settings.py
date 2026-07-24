import base64
import shutil
from pathlib import Path

from httpx import AsyncClient

from app.core.config import get_settings
from app.tests.conftest import auth_headers, login

# Minimal valid 1x1 transparent PNG.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


async def test_get_company_settings_auto_creates_from_store(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.get(
        "/api/v1/settings/company", headers=auth_headers(tokens["access_token"])
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["store_id"] == str(lite_tenant["store"].id)
    assert body["legal_name"]


async def test_patch_company_settings_updates_fields(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    resp = await client.patch(
        "/api/v1/settings/company",
        json={"gstin": "33AAAAA0000A1Z5", "invoice_footer_text": "Thank you, visit again!"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["gstin"] == "33AAAAA0000A1Z5"
    assert body["invoice_footer_text"] == "Thank you, visit again!"


async def test_logo_upload_end_to_end_servable(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    tenant_id = str(lite_tenant["tenant"].id)

    try:
        files = {"file": ("logo.png", _TINY_PNG, "image/png")}
        upload_resp = await client.post(
            "/api/v1/settings/company/logo", files=files, headers=headers
        )
        assert upload_resp.status_code == 200, upload_resp.text
        logo_url = upload_resp.json()["logo_url"]
        assert logo_url.startswith("/media/logos/")

        get_resp = await client.get(
            "/api/v1/settings/company", headers=auth_headers(tokens["access_token"])
        )
        assert get_resp.json()["logo_url"] == logo_url

        served = await client.get(logo_url)
        assert served.status_code == 200
        assert served.content == _TINY_PNG
    finally:
        shutil.rmtree(Path(get_settings().MEDIA_ROOT) / "logos" / tenant_id, ignore_errors=True)


async def test_logo_upload_rejects_non_image(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    files = {"file": ("logo.txt", b"not an image", "text/plain")}
    resp = await client.post(
        "/api/v1/settings/company/logo",
        files=files,
        headers=auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 400
