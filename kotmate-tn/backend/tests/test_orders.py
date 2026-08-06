import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _default_location_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/api/v1/locations", headers=headers)
    return resp.json()[0]["id"]


async def _section_id(client: AsyncClient, headers: dict, name_en: str) -> str:
    resp = await client.get("/api/v1/sections", headers=headers)
    return next(s["id"] for s in resp.json() if s["name_en"] == name_en)


async def _create_category(client: AsyncClient, headers: dict, name_en: str = "Mains") -> dict:
    resp = await client.post("/api/v1/categories", json={"name_en": name_en}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


async def _create_item(client: AsyncClient, headers: dict, category_id: str, **overrides) -> dict:
    payload = {"name_en": "Meals", "category_id": category_id, "price": 100}
    payload.update(overrides)
    resp = await client.post("/api/v1/items", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_table(
    client: AsyncClient, headers: dict, location_id: str, section_id: str, **overrides
) -> dict:
    payload = {"location_id": location_id, "section_id": section_id, "table_number": "T1"}
    payload.update(overrides)
    resp = await client.post("/api/v1/tables", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_order_resolves_base_price_when_no_section_override(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)

    resp = await client.post(
        "/api/v1/orders",
        json={
            "location_id": location_id,
            "section_id": section_id,
            "items": [{"item_id": item["id"], "quantity": 2}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["items"][0]["unit_price"] == 100
    assert body["subtotal"] == 200
    assert body["status"] == "open"


async def test_section_override_price_used_when_present(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    ac_id = await _section_id(client, headers, "AC")
    non_ac_id = await _section_id(client, headers, "Non-AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)

    await client.put(
        f"/api/v1/items/{item['id']}/section-prices",
        json={"prices": [{"section_id": ac_id, "price": 150}]},
        headers=headers,
    )

    ac_order = await client.post(
        "/api/v1/orders",
        json={
            "location_id": location_id,
            "section_id": ac_id,
            "items": [{"item_id": item["id"], "quantity": 1}],
        },
        headers=headers,
    )
    assert ac_order.json()["items"][0]["unit_price"] == 150

    non_ac_order = await client.post(
        "/api/v1/orders",
        json={
            "location_id": location_id,
            "section_id": non_ac_id,
            "items": [{"item_id": item["id"], "quantity": 1}],
        },
        headers=headers,
    )
    assert non_ac_order.json()["items"][0]["unit_price"] == 100


async def test_price_is_snapshotted_not_retroactive(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)

    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "items": [{"item_id": item["id"], "quantity": 1}],
            },
            headers=headers,
        )
    ).json()
    assert order["items"][0]["unit_price"] == 100

    await client.patch(f"/api/v1/items/{item['id']}", json={"price": 999}, headers=headers)

    refetched = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert refetched["items"][0]["unit_price"] == 100


async def test_table_must_belong_to_selected_section(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    ac_id = await _section_id(client, headers, "AC")
    non_ac_id = await _section_id(client, headers, "Non-AC")
    table = await _create_table(client, headers, location_id, ac_id)

    resp = await client.post(
        "/api/v1/orders",
        json={"location_id": location_id, "section_id": non_ac_id, "table_id": table["id"], "items": []},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_hold_and_recall_roundtrip(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=50)
    waiter = (
        await client.post(
            "/api/v1/waiters",
            json={"location_id": location_id, "waiter_number": "W1", "name": "Ravi"},
            headers=headers,
        )
    ).json()

    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "table_id": table["id"],
                "waiter_id": waiter["id"],
                "items": [{"item_id": item["id"], "quantity": 3}],
            },
            headers=headers,
        )
    ).json()

    hold_resp = await client.patch(
        f"/api/v1/orders/{order['id']}",
        json={"status": "held", "hold_label": "Corner table"},
        headers=headers,
    )
    assert hold_resp.status_code == 200
    assert hold_resp.json()["status"] == "held"

    held_list = await client.get("/api/v1/orders", params={"status": "held"}, headers=headers)
    assert any(o["id"] == order["id"] for o in held_list.json())

    recall_resp = await client.patch(
        f"/api/v1/orders/{order['id']}", json={"status": "open"}, headers=headers
    )
    assert recall_resp.status_code == 200
    recalled = recall_resp.json()
    assert recalled["status"] == "open"
    assert recalled["table_id"] == table["id"]
    assert recalled["waiter_id"] == waiter["id"]
    assert recalled["items"][0]["quantity"] == 3


async def test_section_change_dry_run_does_not_persist_then_apply_does(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    ac_id = await _section_id(client, headers, "AC")
    non_ac_id = await _section_id(client, headers, "Non-AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)
    await client.put(
        f"/api/v1/items/{item['id']}/section-prices",
        json={"prices": [{"section_id": ac_id, "price": 150}]},
        headers=headers,
    )

    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": non_ac_id,
                "items": [{"item_id": item["id"], "quantity": 1}],
            },
            headers=headers,
        )
    ).json()
    assert order["items"][0]["unit_price"] == 100

    preview_resp = await client.patch(
        f"/api/v1/orders/{order['id']}?dry_run=true", json={"section_id": ac_id}, headers=headers
    )
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert preview["subtotal_changed"] is True
    assert preview["order"]["items"][0]["unit_price"] == 150

    # Dry run must not have persisted anything.
    unchanged = (await client.get(f"/api/v1/orders/{order['id']}", headers=headers)).json()
    assert unchanged["section_id"] == non_ac_id
    assert unchanged["items"][0]["unit_price"] == 100

    apply_resp = await client.patch(
        f"/api/v1/orders/{order['id']}", json={"section_id": ac_id}, headers=headers
    )
    assert apply_resp.status_code == 200
    applied = apply_resp.json()
    assert applied["section_id"] == ac_id
    assert applied["items"][0]["unit_price"] == 150


async def test_cart_replace_preserves_row_identity_for_unchanged_lines(
    client: AsyncClient, tenant_admin: dict
):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item_a = await _create_item(client, headers, category["id"], name_en="Item A", price=50)
    item_b = await _create_item(client, headers, category["id"], name_en="Item B", price=30)

    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "items": [{"item_id": item_a["id"], "quantity": 1}],
            },
            headers=headers,
        )
    ).json()
    original_line_id = order["items"][0]["id"]

    updated = (
        await client.patch(
            f"/api/v1/orders/{order['id']}",
            json={
                "items": [
                    {"item_id": item_a["id"], "quantity": 1},
                    {"item_id": item_b["id"], "quantity": 2},
                ]
            },
            headers=headers,
        )
    ).json()
    ids_by_item = {line["item_id"]: line["id"] for line in updated["items"]}
    assert ids_by_item[item_a["id"]] == original_line_id
    assert ids_by_item[item_b["id"]] is not None


async def test_waiter_role_order_auto_locks_to_own_linked_waiter(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")

    waiter_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w1", "name": "Waiter One", "role": "waiter", "password": "password123"},
            headers=headers,
        )
    ).json()
    waiter_row = (
        await client.post(
            "/api/v1/waiters",
            json={
                "location_id": location_id,
                "waiter_number": "W9",
                "name": "Waiter One",
                "user_id": waiter_user["id"],
            },
            headers=headers,
        )
    ).json()
    other_waiter_row = (
        await client.post(
            "/api/v1/waiters",
            json={"location_id": location_id, "waiter_number": "W10", "name": "Someone Else"},
            headers=headers,
        )
    ).json()

    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter_user["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    my_profile = await client.get("/api/v1/waiters/me", headers=waiter_headers)
    assert my_profile.json()["id"] == waiter_row["id"]

    # Even trying to assign a different waiter is overridden server-side.
    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "waiter_id": other_waiter_row["id"],
                "items": [],
            },
            headers=waiter_headers,
        )
    ).json()
    assert order["waiter_id"] == waiter_row["id"]


async def test_incentive_preview_computed_from_subtotal(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)
    waiter = (
        await client.post(
            "/api/v1/waiters",
            json={
                "location_id": location_id,
                "waiter_number": "W1",
                "name": "Ravi",
                "incentive_rate": 2,
            },
            headers=headers,
        )
    ).json()

    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "waiter_id": waiter["id"],
                "items": [{"item_id": item["id"], "quantity": 2}],
            },
            headers=headers,
        )
    ).json()
    assert order["subtotal"] == 200
    assert order["waiter_incentive_amount"] == 4.0
    # tenant_admin operating POS directly attributes no cashier incentive (CLAUDE.md §11).
    assert order["cashier_incentive_amount"] is None


async def test_inactive_or_foreign_item_rejected(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=100)
    await client.patch(f"/api/v1/items/{item['id']}", json={"is_active": False}, headers=headers)

    resp = await client.post(
        "/api/v1/orders",
        json={
            "location_id": location_id,
            "section_id": section_id,
            "items": [{"item_id": item["id"], "quantity": 1}],
        },
        headers=headers,
    )
    assert resp.status_code == 400


async def test_kitchen_role_blocked_from_orders(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")

    kot_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "kot01", "name": "Kitchen", "role": "kitchen", "password": "password123"},
            headers=headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": kot_user["user_id"], "password": "password123"}
    )
    kitchen_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.post(
        "/api/v1/orders",
        json={"location_id": location_id, "section_id": section_id, "items": []},
        headers=kitchen_headers,
    )
    assert resp.status_code == 403
