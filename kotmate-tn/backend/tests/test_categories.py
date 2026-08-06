import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_category_appends_display_order(client: AsyncClient, tenant_admin: dict):
    first = await client.post(
        "/api/v1/categories",
        json={"name_en": "Starters", "name_ta": "தொடக்கம்"},
        headers=tenant_admin["headers"],
    )
    assert first.status_code == 201
    assert first.json()["name_ta"] == "தொடக்கம்"

    second = await client.post(
        "/api/v1/categories", json={"name_en": "Mains"}, headers=tenant_admin["headers"]
    )
    assert second.status_code == 201
    assert second.json()["display_order"] > first.json()["display_order"]


async def test_update_category(client: AsyncClient, tenant_admin: dict):
    create_resp = await client.post(
        "/api/v1/categories", json={"name_en": "Desserts"}, headers=tenant_admin["headers"]
    )
    category = create_resp.json()

    update_resp = await client.patch(
        f"/api/v1/categories/{category['id']}",
        json={"name_en": "Sweets", "is_active": False},
        headers=tenant_admin["headers"],
    )
    assert update_resp.status_code == 200
    body = update_resp.json()
    assert body["name_en"] == "Sweets"
    assert body["is_active"] is False


async def test_reorder_categories(client: AsyncClient, tenant_admin: dict):
    a = (
        await client.post("/api/v1/categories", json={"name_en": "A"}, headers=tenant_admin["headers"])
    ).json()
    b = (
        await client.post("/api/v1/categories", json={"name_en": "B"}, headers=tenant_admin["headers"])
    ).json()

    reorder_resp = await client.put(
        "/api/v1/categories/reorder",
        json={"categories": [{"id": a["id"], "display_order": 5}, {"id": b["id"], "display_order": 1}]},
        headers=tenant_admin["headers"],
    )
    assert reorder_resp.status_code == 200
    ordered_ids = [c["id"] for c in reorder_resp.json()]
    assert ordered_ids.index(b["id"]) < ordered_ids.index(a["id"])


async def test_reorder_rejects_foreign_category_id(client: AsyncClient, tenant_admin: dict):
    resp = await client.put(
        "/api/v1/categories/reorder",
        json={"categories": [{"id": "00000000-0000-0000-0000-000000000000", "display_order": 1}]},
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 400


async def test_non_tenant_admin_can_read_but_not_write_categories(client: AsyncClient, tenant_admin: dict):
    waiter = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w1", "name": "W1", "role": "waiter", "password": "password123"},
            headers=tenant_admin["headers"],
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    list_resp = await client.get("/api/v1/categories", headers=waiter_headers)
    assert list_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/categories", json={"name_en": "Blocked"}, headers=waiter_headers
    )
    assert create_resp.status_code == 403
