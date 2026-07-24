from httpx import AsyncClient

from app.tests.conftest import auth_headers, login


async def test_create_standard_slab_has_no_warning(client: AsyncClient, lite_tenant: dict) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.post(
        "/api/v1/settings/tax-profiles",
        json={"name": "GST 18%", "cgst_pct": 9, "sgst_pct": 9},
        headers=auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["warning"] is None


async def test_create_nonstandard_slab_returns_warning_not_rejection(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    resp = await client.post(
        "/api/v1/settings/tax-profiles",
        json={"name": "Custom 10%", "cgst_pct": 5, "sgst_pct": 5},
        headers=auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["warning"] is not None


async def test_setting_new_default_unsets_previous_default(
    client: AsyncClient, lite_tenant: dict
) -> None:
    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])

    first = await client.post(
        "/api/v1/settings/tax-profiles",
        json={"name": "GST 5%", "cgst_pct": 2.5, "sgst_pct": 2.5, "is_default": True},
        headers=headers,
    )
    first_id = first.json()["id"]
    assert first.json()["is_default"] is True

    second = await client.post(
        "/api/v1/settings/tax-profiles",
        json={"name": "GST 18%", "cgst_pct": 9, "sgst_pct": 9, "is_default": True},
        headers=headers,
    )
    assert second.json()["is_default"] is True

    listing = await client.get("/api/v1/settings/tax-profiles", headers=headers)
    first_after = next(p for p in listing.json() if p["id"] == first_id)
    assert first_after["is_default"] is False


async def test_delete_tax_profile_referenced_by_item_fails(
    client: AsyncClient, lite_tenant: dict
) -> None:
    from app.tests.conftest import create_category_and_tax_profile

    tokens = await login(client, "admin@tenanta.dev", "Admin@123")
    headers = auth_headers(tokens["access_token"])
    category_id, tax_profile_id = await create_category_and_tax_profile(client, headers)

    await client.post(
        "/api/v1/items",
        json={
            "category_id": category_id,
            "name_en": "Rice 5kg",
            "name_ta": "அரிசி 5kg",
            "unit": "kg",
            "mrp_paise": 40000,
            "selling_price_paise": 38000,
            "cost_price_paise": 35000,
            "tax_profile_id": tax_profile_id,
        },
        headers=headers,
    )

    resp = await client.delete(f"/api/v1/settings/tax-profiles/{tax_profile_id}", headers=headers)
    assert resp.status_code == 409
