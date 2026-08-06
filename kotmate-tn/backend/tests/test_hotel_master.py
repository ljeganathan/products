import io

import pytest
from httpx import AsyncClient

import app.services.bill_service as bill_service
import app.services.kot_service as kot_service

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
    payload = {"name_en": "Meals", "name_ta": "சாப்பாடு", "category_id": category_id, "price": 100}
    payload.update(overrides)
    resp = await client.post("/api/v1/items", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_order(
    client: AsyncClient, headers: dict, location_id: str, section_id: str, items: list[dict]
) -> dict:
    resp = await client.post(
        "/api/v1/orders",
        json={"location_id": location_id, "section_id": section_id, "items": items},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _hotel_payload(**overrides) -> dict:
    payload = {
        "location_id": None,
        "name": "Test Hotel",
        "door_no": "1",
        "street": "Main St",
        "city": "Chennai",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "pincode": "600001",
        "phone": "9840000000",
        "gstin": None,
        "upi_id": "hotel@upi",
        "show_tamil_names": True,
    }
    payload.update(overrides)
    return payload


# --- API integration tests ---
# (Pure show_tamil_names formatter behavior is covered in test_billing_calc.py; these
# tests cover the DB-backed wiring — hotel_master's saved value actually reaching the
# print dispatch call for both KOT and Bill.)


async def test_hotel_master_upsert_roundtrip(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)

    empty = await client.get(
        "/api/v1/settings/hotel-master", params={"location_id": location_id}, headers=headers
    )
    assert empty.status_code == 200
    assert empty.json()["name"] is None

    saved = await client.put(
        "/api/v1/settings/hotel-master", json=_hotel_payload(location_id=location_id), headers=headers
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["name"] == "Test Hotel"
    assert body["upi_id"] == "hotel@upi"

    refetched = await client.get(
        "/api/v1/settings/hotel-master", params={"location_id": location_id}, headers=headers
    )
    assert refetched.json()["name"] == "Test Hotel"


async def test_gstin_state_mismatch_warns_but_does_not_block(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)

    mismatched = await client.put(
        "/api/v1/settings/hotel-master",
        json=_hotel_payload(location_id=location_id, gstin="27ABCDE1234F1Z5", state="Tamil Nadu"),
        headers=headers,
    )
    assert mismatched.status_code == 200
    body = mismatched.json()
    assert body["gstin_state_warning"] is not None
    assert "Maharashtra" in body["gstin_state_warning"]

    matched = await client.put(
        "/api/v1/settings/hotel-master",
        json=_hotel_payload(location_id=location_id, gstin="33ABCDE1234F1Z5", state="Tamil Nadu"),
        headers=headers,
    )
    assert matched.status_code == 200
    assert matched.json()["gstin_state_warning"] is None


async def test_hotel_master_logo_upload(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)

    fake_png = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    resp = await client.post(
        f"/api/v1/settings/hotel-master/{location_id}/logo",
        files={"file": ("logo.png", fake_png, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["logo_url"] is not None


async def test_non_tenant_admin_can_read_but_not_write_hotel_master(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    waiter = (
        await client.post(
            "/api/v1/users",
            json={"local_handle": "w1", "name": "W1", "role": "waiter", "password": "password123"},
            headers=headers,
        )
    ).json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": waiter["user_id"], "password": "password123"}
    )
    waiter_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert (
        await client.get(
            "/api/v1/settings/hotel-master", params={"location_id": location_id}, headers=waiter_headers
        )
    ).status_code == 200
    write_resp = await client.put(
        "/api/v1/settings/hotel-master", json=_hotel_payload(location_id=location_id), headers=waiter_headers
    )
    assert write_resp.status_code == 403


async def test_kot_print_passes_through_hotel_show_tamil_names(
    client: AsyncClient, pro_max_tenant_admin: dict, monkeypatch
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")

    await client.put(
        "/api/v1/settings/hotel-master",
        json=_hotel_payload(location_id=location_id, show_tamil_names=False),
        headers=headers,
    )
    await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Kitchen Printer",
            "target": "kot",
            "printer_type": "thermal",
            "connection_type": "network",
        },
        headers=headers,
    )

    captured = {}

    def _spy(printer, render_data):
        captured["show_tamil_names"] = render_data.show_tamil_names

    monkeypatch.setattr(kot_service, "dispatch_kot_print", _spy)

    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=50)
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )
    resp = await client.post("/api/v1/kot", json={"order_id": order["id"]}, headers=headers)
    assert resp.status_code == 201
    assert captured["show_tamil_names"] is False


async def test_bill_print_passes_through_hotel_show_tamil_names(
    client: AsyncClient, pro_max_tenant_admin: dict, monkeypatch
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")

    await client.put(
        "/api/v1/settings/hotel-master",
        json=_hotel_payload(location_id=location_id, show_tamil_names=False),
        headers=headers,
    )
    await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Bill Printer",
            "target": "bill",
            "printer_type": "thermal",
            "connection_type": "network",
        },
        headers=headers,
    )

    captured = {}

    def _spy(printer, render_data):
        captured["show_tamil_names"] = render_data.show_tamil_names

    monkeypatch.setattr(bill_service, "dispatch_bill_print", _spy)

    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=50)
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )
    resp = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 50.0}]},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert captured["show_tamil_names"] is False
