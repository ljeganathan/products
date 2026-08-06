import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_default_sections_seeded_at_onboarding(client: AsyncClient, tenant_admin: dict):
    resp = await client.get("/api/v1/sections", headers=tenant_admin["headers"])
    assert resp.status_code == 200
    sections = resp.json()
    names = {s["name_en"]: s["is_seating"] for s in sections}
    assert names == {
        "AC": True,
        "Non-AC": True,
        "Rooftop": True,
        "Family": True,
        "Takeaway": False,
        "Online Delivery": False,
    }


async def test_create_section_appends_display_order(client: AsyncClient, tenant_admin: dict):
    existing = (await client.get("/api/v1/sections", headers=tenant_admin["headers"])).json()
    max_order = max(s["display_order"] for s in existing)

    resp = await client.post(
        "/api/v1/sections", json={"name_en": "Garden", "is_seating": True}, headers=tenant_admin["headers"]
    )
    assert resp.status_code == 201
    assert resp.json()["display_order"] > max_order


async def test_update_section_rename_and_deactivate(client: AsyncClient, tenant_admin: dict):
    sections = (await client.get("/api/v1/sections", headers=tenant_admin["headers"])).json()
    ac = next(s for s in sections if s["name_en"] == "AC")

    resp = await client.patch(
        f"/api/v1/sections/{ac['id']}",
        json={"name_ta": "குளிர்சாதன", "is_active": False},
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["name_ta"] == "குளிர்சாதன"
    assert resp.json()["is_active"] is False


async def test_reorder_sections(client: AsyncClient, tenant_admin: dict):
    sections = (await client.get("/api/v1/sections", headers=tenant_admin["headers"])).json()
    first, second = sections[0], sections[1]

    resp = await client.put(
        "/api/v1/sections/reorder",
        json={
            "sections": [
                {"id": first["id"], "display_order": second["display_order"]},
                {"id": second["id"], "display_order": first["display_order"]},
            ]
        },
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 200
    reordered = {s["id"]: s["display_order"] for s in resp.json()}
    assert reordered[first["id"]] == second["display_order"]
    assert reordered[second["id"]] == first["display_order"]


async def test_pos_sections_endpoint_excludes_inactive(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    sections = (await client.get("/api/v1/sections", headers=headers)).json()
    ac = next(s for s in sections if s["name_en"] == "AC")
    await client.patch(f"/api/v1/sections/{ac['id']}", json={"is_active": False}, headers=headers)

    resp = await client.get("/api/v1/sections/pos", headers=headers)
    assert resp.status_code == 200
    names = [s["name_en"] for s in resp.json()]
    assert "AC" not in names
    # Both seating and non-seating sections are included — POS needs Takeaway too.
    assert "Takeaway" in names
    assert "Non-AC" in names


async def test_non_tenant_admin_can_read_but_not_write_sections(client: AsyncClient, tenant_admin: dict):
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

    list_resp = await client.get("/api/v1/sections", headers=waiter_headers)
    assert list_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/sections", json={"name_en": "Blocked"}, headers=waiter_headers
    )
    assert create_resp.status_code == 403
