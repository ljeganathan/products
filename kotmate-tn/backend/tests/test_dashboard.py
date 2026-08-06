from datetime import date

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

TODAY = date.today().isoformat()


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
    payload = {"name_en": "Meals", "category_id": category_id, "price": 200}
    payload.update(overrides)
    resp = await client.post("/api/v1/items", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _bill_simple_order(
    client: AsyncClient, headers: dict, location_id: str, section_id: str, item_id: str
) -> dict:
    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "items": [{"item_id": item_id, "quantity": 1}],
            },
            headers=headers,
        )
    ).json()
    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "upi", "amount": 200.0}]},
        headers=headers,
    )
    assert bill.status_code == 201, bill.text
    return bill.json()


async def test_dashboard_summary_reconciles_with_bills(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=200)

    bill1 = await _bill_simple_order(client, headers, location_id, section_id, item["id"])
    bill2 = await _bill_simple_order(client, headers, location_id, section_id, item["id"])

    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["bill_count"] == 2
    assert body["today_sales"] == bill1["grand_total"] + bill2["grand_total"]
    assert body["average_bill_value"] == round(body["today_sales"] / 2, 2)
    assert any(i["item_id"] == item["id"] and i["quantity_sold"] == 2 for i in body["top_items"])
    assert len(body["hourly_trend"]) == 24
    assert sum(h["sales"] for h in body["hourly_trend"]) == body["today_sales"]


async def test_dashboard_summary_available_on_lite(client: AsyncClient, tenant_admin: dict):
    resp = await client.get("/api/v1/dashboard/summary", headers=tenant_admin["headers"])
    assert resp.status_code == 200


async def test_multi_location_comparison_pro_max_only(
    client: AsyncClient, tenant_admin: dict, pro_tenant_admin: dict, pro_max_tenant_admin: dict
):
    lite_resp = await client.get(
        "/api/v1/dashboard/multi-location",
        params={"date_from": TODAY, "date_to": TODAY},
        headers=tenant_admin["headers"],
    )
    assert lite_resp.status_code == 403

    pro_resp = await client.get(
        "/api/v1/dashboard/multi-location",
        params={"date_from": TODAY, "date_to": TODAY},
        headers=pro_tenant_admin["headers"],
    )
    assert pro_resp.status_code == 403

    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=200)
    await _bill_simple_order(client, headers, location_id, section_id, item["id"])

    second_location = (
        await client.post(
            "/api/v1/locations",
            json={"name": "Branch Two", "state": "Tamil Nadu", "pincode": "600002"},
            headers=headers,
        )
    ).json()

    pro_max_resp = await client.get(
        "/api/v1/dashboard/multi-location",
        params={"date_from": TODAY, "date_to": TODAY},
        headers=headers,
    )
    assert pro_max_resp.status_code == 200, pro_max_resp.text
    rows = pro_max_resp.json()["rows"]
    main_row = next(r for r in rows if r["location_id"] == location_id)
    assert main_row["sales"] == 200.0
    assert main_row["bill_count"] == 1
    # Second location has no bills yet — it legitimately doesn't appear (an inner join
    # on Bill), not a bug; this just confirms it doesn't show phantom zero-sales noise.
    assert not any(r["location_id"] == second_location["id"] for r in rows)


async def test_waiter_role_blocked_from_dashboard(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    waiter_user = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w1", "name": "W1", "role": "waiter", "password": "password123"},
            headers=headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter_user["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/dashboard/summary", headers=waiter_headers)
    assert resp.status_code == 403
