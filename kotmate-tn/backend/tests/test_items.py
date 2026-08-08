import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _create_category(client: AsyncClient, headers: dict, name_en: str = "Mains") -> dict:
    resp = await client.post("/api/v1/categories", json={"name_en": name_en}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _create_item(client: AsyncClient, headers: dict, category_id: str, **overrides) -> dict:
    payload = {"name_en": "Meals", "name_ta": "சாப்பாடு", "category_id": category_id, "price": 120}
    payload.update(overrides)
    resp = await client.post("/api/v1/items", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_item_with_tamil_name_and_read_back(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    item = await _create_item(client, tenant_admin["headers"], category["id"], item_code="301")

    list_resp = await client.get("/api/v1/items", headers=tenant_admin["headers"])
    assert list_resp.status_code == 200
    ids = [i["id"] for i in list_resp.json()]
    assert item["id"] in ids

    found = next(i for i in list_resp.json() if i["id"] == item["id"])
    assert found["name_ta"] == "சாப்பாடு"
    assert found["item_code"] == "301"


async def test_item_code_must_be_unique_per_tenant(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    await _create_item(client, tenant_admin["headers"], category["id"], item_code="100")

    dup = await client.post(
        "/api/v1/items",
        json={"name_en": "Coffee", "category_id": category["id"], "price": 20, "item_code": "100"},
        headers=tenant_admin["headers"],
    )
    assert dup.status_code == 409


async def test_category_id_must_belong_to_tenant(client: AsyncClient, tenant_admin: dict):
    resp = await client.post(
        "/api/v1/items",
        json={
            "name_en": "Ghost Item",
            "category_id": "00000000-0000-0000-0000-000000000000",
            "price": 50,
        },
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 400


async def test_available_qty_requires_track_inventory(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    resp = await client.post(
        "/api/v1/items",
        json={
            "name_en": "Filter Coffee",
            "category_id": category["id"],
            "price": 20,
            "track_inventory": False,
            "available_qty": 10,
        },
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 422


async def test_restock_rejected_when_not_tracking(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    item = await _create_item(client, tenant_admin["headers"], category["id"])

    resp = await client.patch(
        f"/api/v1/items/{item['id']}/restock", json={"available_qty": 5}, headers=tenant_admin["headers"]
    )
    assert resp.status_code == 409


async def test_restock_succeeds_when_tracking_enabled(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    item = await _create_item(
        client, tenant_admin["headers"], category["id"], track_inventory=True, available_qty=3
    )

    resp = await client.patch(
        f"/api/v1/items/{item['id']}/restock", json={"available_qty": 20}, headers=tenant_admin["headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["available_qty"] == 20


async def test_toggling_track_inventory_off_clears_available_qty(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    item = await _create_item(
        client, tenant_admin["headers"], category["id"], track_inventory=True, available_qty=8
    )
    assert item["available_qty"] == 8

    update_resp = await client.patch(
        f"/api/v1/items/{item['id']}", json={"track_inventory": False}, headers=tenant_admin["headers"]
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["track_inventory"] is False
    assert update_resp.json()["available_qty"] is None

    # Turning tracking back on does not resurrect the old count.
    reenable_resp = await client.patch(
        f"/api/v1/items/{item['id']}", json={"track_inventory": True}, headers=tenant_admin["headers"]
    )
    assert reenable_resp.status_code == 200
    assert reenable_resp.json()["available_qty"] is None


async def test_export_csv_blocked_on_lite_plan(client: AsyncClient, tenant_admin: dict):
    resp = await client.get("/api/v1/items/export.csv", headers=tenant_admin["headers"])
    assert resp.status_code == 403


async def test_export_csv_on_pro_plan(client: AsyncClient, pro_tenant_admin: dict):
    headers = pro_tenant_admin["headers"]
    category = await _create_category(client, headers, name_en="Tiffin")
    await _create_item(client, headers, category["id"], name_en="Dosai", price=60, item_code="401")

    resp = await client.get("/api/v1/items/export.csv", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert "item_code,name_en,name_ta,category,price,tax_class" in body.splitlines()[0]
    assert "401,Dosai" in body


async def test_import_csv_blocked_on_pro_plan(client: AsyncClient, pro_tenant_admin: dict):
    headers = pro_tenant_admin["headers"]
    csv_bytes = b"item_code,name_en,name_ta,category,price,tax_class,is_top_seller,is_combo_tile\n"
    resp = await client.post(
        "/api/v1/items/import.csv",
        files={"file": ("items.csv", csv_bytes, "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 403


async def test_import_csv_creates_and_updates_on_pro_max_plan(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    category = await _create_category(client, headers, name_en="Beverages")
    existing = await _create_item(
        client, headers, category["id"], name_en="Old Coffee", price=15, item_code="501"
    )

    csv_text = (
        "item_code,name_en,name_ta,category,price,tax_class,is_top_seller,is_combo_tile\n"
        f"501,Filter Coffee,{'':s},Beverages,25,,false,false\n"
        "502,Badam Milk,பாதம் பால்,Beverages,40,,true,false\n"
        "999,Ghost,,Unknown Category,10,,false,false\n"
    )

    resp = await client.post(
        "/api/v1/items/import.csv",
        files={"file": ("items.csv", csv_text.encode("utf-8"), "text/csv")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["updated"] == 1
    assert len(body["errors"]) == 1
    assert "Unknown Category" in body["errors"][0]

    list_resp = await client.get("/api/v1/items", headers=headers)
    items_by_code = {i["item_code"]: i for i in list_resp.json()}
    assert items_by_code["501"]["name_en"] == "Filter Coffee"
    assert items_by_code["501"]["price"] == 25
    assert items_by_code["501"]["id"] == existing["id"]
    assert items_by_code["502"]["name_en"] == "Badam Milk"
    assert items_by_code["502"]["is_top_seller"] is True


async def test_lite_tenant_blocked_from_image_upload(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    item = await _create_item(client, tenant_admin["headers"], category["id"])

    resp = await client.post(
        f"/api/v1/items/{item['id']}/image",
        files={"file": ("photo.png", b"fake-image-bytes", "image/png")},
        headers=tenant_admin["headers"],
    )
    assert resp.status_code == 403
    assert "upgrade" in resp.json()["detail"].lower()


async def test_pro_max_tenant_can_upload_image(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"])

    resp = await client.post(
        f"/api/v1/items/{item['id']}/image",
        files={"file": ("photo.png", b"fake-image-bytes", "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["image_url"] is not None
    assert "/uploads/" in resp.json()["image_url"]


async def test_lite_tenant_blocked_from_section_price_override(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    item = await _create_item(client, tenant_admin["headers"], category["id"], price=100)

    sections_resp = await client.get(
        f"/api/v1/items/{item['id']}/section-prices", headers=tenant_admin["headers"]
    )
    assert sections_resp.status_code == 200
    sections = sections_resp.json()
    assert len(sections) > 0
    assert all(s["resolved_price"] == 100 for s in sections)

    write_resp = await client.put(
        f"/api/v1/items/{item['id']}/section-prices",
        json={"prices": [{"section_id": sections[0]["section_id"], "price": 150}]},
        headers=tenant_admin["headers"],
    )
    assert write_resp.status_code == 403


async def test_pro_max_section_override_affects_only_that_section(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)

    sections = (
        await client.get(f"/api/v1/items/{item['id']}/section-prices", headers=headers)
    ).json()
    assert len(sections) >= 2
    target_section = sections[0]["section_id"]
    other_section = sections[1]["section_id"]

    write_resp = await client.put(
        f"/api/v1/items/{item['id']}/section-prices",
        json={"prices": [{"section_id": target_section, "price": 150}]},
        headers=headers,
    )
    assert write_resp.status_code == 200
    updated = {s["section_id"]: s for s in write_resp.json()}
    assert updated[target_section]["resolved_price"] == 150
    assert updated[target_section]["override_price"] == 150
    assert updated[other_section]["resolved_price"] == 100
    assert updated[other_section]["override_price"] is None

    # Clearing the override (price=None) falls back to base price.
    clear_resp = await client.put(
        f"/api/v1/items/{item['id']}/section-prices",
        json={"prices": [{"section_id": target_section, "price": None}]},
        headers=headers,
    )
    assert clear_resp.status_code == 200
    cleared = {s["section_id"]: s for s in clear_resp.json()}
    assert cleared[target_section]["resolved_price"] == 100
    assert cleared[target_section]["override_price"] is None


async def test_search_and_category_filter(client: AsyncClient, tenant_admin: dict):
    mains = await _create_category(client, tenant_admin["headers"], name_en="Mains")
    drinks = await _create_category(client, tenant_admin["headers"], name_en="Drinks")
    await _create_item(client, tenant_admin["headers"], mains["id"], name_en="Chicken Biryani")
    await _create_item(client, tenant_admin["headers"], drinks["id"], name_en="Filter Coffee")

    search_resp = await client.get(
        "/api/v1/items", params={"search": "Biryani"}, headers=tenant_admin["headers"]
    )
    assert search_resp.status_code == 200
    names = [i["name_en"] for i in search_resp.json()]
    assert names == ["Chicken Biryani"]

    filter_resp = await client.get(
        "/api/v1/items", params={"category_id": drinks["id"]}, headers=tenant_admin["headers"]
    )
    assert filter_resp.status_code == 200
    names = [i["name_en"] for i in filter_resp.json()]
    assert names == ["Filter Coffee"]


async def test_non_tenant_admin_can_read_but_not_write_items(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
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

    list_resp = await client.get("/api/v1/items", headers=waiter_headers)
    assert list_resp.status_code == 200

    create_resp = await client.post(
        "/api/v1/items",
        json={"name_en": "Blocked", "category_id": category["id"], "price": 10},
        headers=waiter_headers,
    )
    assert create_resp.status_code == 403


async def test_fuzzy_search_endpoint_tolerates_typos(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    await _create_item(client, tenant_admin["headers"], category["id"], name_en="Chicken Biryani")
    await _create_item(client, tenant_admin["headers"], category["id"], name_en="Filter Coffee")

    resp = await client.get(
        "/api/v1/items/search", params={"q": "biriyani"}, headers=tenant_admin["headers"]
    )
    assert resp.status_code == 200
    names = [i["name_en"] for i in resp.json()]
    assert "Chicken Biryani" in names


async def test_search_matches_short_realistic_prefix(client: AsyncClient, tenant_admin: dict):
    """POS-37 regression: trigram similarity alone scores "cof" vs "Filter Coffee" at
    0.2, under pg_trgm's 0.3 default threshold — a cashier typing the first few letters
    of an item got zero results. Substring matching must catch this even though it's not
    a typo case.
    """
    category = await _create_category(client, tenant_admin["headers"])
    await _create_item(client, tenant_admin["headers"], category["id"], name_en="Filter Coffee")

    resp = await client.get(
        "/api/v1/items/search", params={"q": "cof"}, headers=tenant_admin["headers"]
    )
    assert resp.status_code == 200
    names = [i["name_en"] for i in resp.json()]
    assert "Filter Coffee" in names


async def test_get_item_by_exact_code(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    item = await _create_item(client, tenant_admin["headers"], category["id"], item_code="301")

    resp = await client.get("/api/v1/items/by-code/301", headers=tenant_admin["headers"])
    assert resp.status_code == 200
    assert resp.json()["id"] == item["id"]

    missing_resp = await client.get("/api/v1/items/by-code/999", headers=tenant_admin["headers"])
    assert missing_resp.status_code == 404


async def test_top_sellers_endpoint(client: AsyncClient, tenant_admin: dict):
    category = await _create_category(client, tenant_admin["headers"])
    top_item = await _create_item(
        client, tenant_admin["headers"], category["id"], name_en="Full Meals", is_top_seller=True
    )
    await _create_item(client, tenant_admin["headers"], category["id"], name_en="Filter Coffee")

    resp = await client.get("/api/v1/items/top-sellers", headers=tenant_admin["headers"])
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()]
    assert top_item["id"] in ids
    assert all(i["is_top_seller"] for i in resp.json())


async def test_top_sellers_backfills_from_recent_sales_when_none_pinned(
    client: AsyncClient, tenant_admin: dict
):
    """POS-31: with nothing manually pinned, a recently-billed item must still appear —
    previously the tab was 100% manual and stayed empty/stale regardless of sales.
    """
    headers = tenant_admin["headers"]
    category = await _create_category(client, headers)
    unpinned = await _create_item(client, headers, category["id"], name_en="Chicken 65", price=150)

    location_id = (await client.get("/api/v1/locations", headers=headers)).json()[0]["id"]
    section_id = next(
        s["id"] for s in (await client.get("/api/v1/sections", headers=headers)).json() if s["name_en"] == "AC"
    )
    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "items": [{"item_id": unpinned["id"], "quantity": 3}],
            },
            headers=headers,
        )
    ).json()
    await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "upi", "amount": order["subtotal"]}]},
        headers=headers,
    )

    resp = await client.get("/api/v1/items/top-sellers", headers=headers)
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()]
    assert unpinned["id"] in ids
