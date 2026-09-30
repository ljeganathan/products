"""Phase 28 — Razorpay online payment for QR self-orders. The gateway's HTTP layer is
replaced with an in-memory fake, so these run offline and never touch real Razorpay.
"""

import hashlib
import hmac
import json
import uuid

import pytest
from httpx import AsyncClient

from app.services.payment_gateway import RazorpayGateway
from tests.test_guest_ordering import (
    _create_category,
    _create_item,
    _create_table,
    _default_location_id,
    _enable_qr_self_order,
    _generate_qr,
    _guest_headers,
    _section_id,
    _set_guest_profile,
    _start_guest_session,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

KEY_ID = "rzp_test_abc123"
KEY_SECRET = "shhh-secret"
WEBHOOK_SECRET = "whsec-test"


class FakeRazorpay:
    def __init__(self) -> None:
        self.payments: dict[str, list[dict]] = {}
        self.created: list[dict] = []

    async def request(self, _self, method: str, path: str, body: dict | None = None) -> dict:
        if method == "POST" and path == "/orders":
            order_id = f"order_{uuid.uuid4().hex[:12]}"
            self.created.append({"id": order_id, **(body or {})})
            self.payments[order_id] = []
            return {"id": order_id, "amount": body["amount"], "status": "created"}
        if method == "GET" and path.startswith("/orders/") and path.endswith("/payments"):
            return {"items": self.payments.get(path.split("/")[2], [])}
        if method == "GET" and path.startswith("/orders"):
            return {"items": []}
        if method == "POST" and path.endswith("/capture"):
            pay_id = path.split("/")[2]
            for items in self.payments.values():
                for p in items:
                    if p["id"] == pay_id:
                        p["status"] = "captured"
                        return p
        raise AssertionError(f"unexpected gateway call {method} {path}")

    def pay(self, order_id: str, amount_paise: int, status: str = "captured", **extra) -> str:
        pay_id = f"pay_{uuid.uuid4().hex[:10]}"
        self.payments[order_id].append(
            {
                "id": pay_id,
                "order_id": order_id,
                "amount": amount_paise,
                "status": status,
                "method": "upi",
                **extra,
            }
        )
        return pay_id


@pytest.fixture
def fake_gateway(monkeypatch):
    fake = FakeRazorpay()

    async def _request(self, method, path, body=None):
        return await fake.request(self, method, path, body)

    monkeypatch.setattr(RazorpayGateway, "_request", _request)
    return fake


async def _configure(client: AsyncClient, headers: dict, enabled: bool = True) -> dict:
    resp = await client.put(
        "/api/v1/settings/online-payments",
        json={
            "key_id": KEY_ID,
            "key_secret": KEY_SECRET,
            "webhook_secret": WEBHOOK_SECRET,
            "enabled": enabled,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _guest_with_order(client: AsyncClient, headers: dict, price: int = 100):
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_qr(client, headers, table["id"])
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=price)
    guest = _guest_headers(await _start_guest_session(client, qr_token))
    await _set_guest_profile(client, guest)
    cart = await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )
    assert cart.status_code == 200, cart.text
    return guest, cart.json(), item


async def test_settings_never_expose_secrets_and_need_keys_to_enable(
    client: AsyncClient, pro_max_tenant_admin: dict, tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    early = await client.put("/api/v1/settings/online-payments", json={"enabled": True}, headers=headers)
    assert early.status_code == 400

    body = await _configure(client, headers)
    assert body["enabled"] is True and body["has_secret"] is True and body["is_test_mode"] is True
    assert body["key_id"] == KEY_ID
    assert KEY_SECRET not in json.dumps(body) and WEBHOOK_SECRET not in json.dumps(body)
    assert "/api/v1/webhooks/razorpay/" in body["webhook_url"]
    uuid.UUID(body["webhook_url"][-36:])  # ends with the tenant id

    # Toggling off keeps the stored keys.
    off = await client.put("/api/v1/settings/online-payments", json={"enabled": False}, headers=headers)
    assert off.json()["enabled"] is False and off.json()["has_secret"] is True

    # Lite plan can't turn it on.
    lite = await client.put(
        "/api/v1/settings/online-payments",
        json={"key_id": KEY_ID, "key_secret": KEY_SECRET},
        headers=tenant_admin["headers"],
    )
    assert lite.status_code == 403


async def test_test_connection_calls_gateway(client: AsyncClient, pro_max_tenant_admin: dict, fake_gateway):
    headers = pro_max_tenant_admin["headers"]
    await _configure(client, headers, enabled=False)
    resp = await client.post("/api/v1/settings/online-payments/test", headers=headers)
    assert resp.status_code == 200 and resp.json() == {"ok": True, "is_test_mode": True}


async def test_guest_pays_online_and_staff_sees_verified_payment(
    client: AsyncClient, pro_max_tenant_admin: dict, fake_gateway
):
    headers = pro_max_tenant_admin["headers"]
    await _configure(client, headers)
    guest, order, _ = await _guest_with_order(client, headers, price=100)

    preview = await client.get("/api/v1/guest/bill-preview", headers=guest)
    assert preview.json()["online_payment"]["enabled"] is True
    assert preview.json()["online_payment"]["key_id"] == KEY_ID
    assert preview.json()["online_payment"]["paid"] is False

    created = await client.post("/api/v1/guest/payments/create", headers=guest)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["amount_paise"] == 10000 and body["currency"] == "INR" and body["key_id"] == KEY_ID
    # The amount was taken from the server-side bill, not from anything the client sent.
    assert fake_gateway.created[-1]["amount"] == 10000

    pending = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert pending.json()["status"] == "created"

    # A payment for the wrong amount must not mark the order paid.
    fake_gateway.pay(body["provider_order_id"], 5000)
    still = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert still.json()["status"] == "created"

    pay_id = fake_gateway.pay(body["provider_order_id"], 10000)
    paid = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert paid.json()["status"] == "paid" and paid.json()["reference"] == pay_id

    # Staff Finalize screen sees it.
    staff_preview = await client.post(
        "/api/v1/bills/preview", json={"order_id": order["id"]}, headers=headers
    )
    assert staff_preview.json()["online_paid_amount"] == 100
    assert staff_preview.json()["online_payment_reference"] == pay_id

    # Cart is locked once paid; a second payment attempt is refused.
    locked = await client.post("/api/v1/guest/cart", json={"items": []}, headers=guest)
    assert locked.status_code == 409
    again = await client.post("/api/v1/guest/payments/create", headers=guest)
    assert again.status_code == 409

    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "upi", "amount": 100}]},
        headers=headers,
    )
    assert bill.status_code == 201, bill.text


async def test_authorized_payment_is_captured(client: AsyncClient, pro_max_tenant_admin: dict, fake_gateway):
    headers = pro_max_tenant_admin["headers"]
    await _configure(client, headers)
    guest, _, _ = await _guest_with_order(client, headers, price=50)
    body = (await client.post("/api/v1/guest/payments/create", headers=guest)).json()
    fake_gateway.pay(body["provider_order_id"], 5000, status="authorized")
    result = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert result.json()["status"] == "paid"


async def test_failed_payment_reports_reason_then_retry_works(
    client: AsyncClient, pro_max_tenant_admin: dict, fake_gateway
):
    headers = pro_max_tenant_admin["headers"]
    await _configure(client, headers)
    guest, _, _ = await _guest_with_order(client, headers, price=70)
    first = (await client.post("/api/v1/guest/payments/create", headers=guest)).json()
    fake_gateway.pay(first["provider_order_id"], 7000, status="failed", error_description="Bank declined")
    failed = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert failed.json()["status"] == "failed" and failed.json()["failure_reason"] == "Bank declined"

    second = await client.post("/api/v1/guest/payments/create", headers=guest)
    assert second.status_code == 200
    assert second.json()["provider_order_id"] != first["provider_order_id"]


async def test_webhook_requires_valid_signature_and_marks_paid(
    client: AsyncClient, pro_max_tenant_admin: dict, fake_gateway
):
    headers = pro_max_tenant_admin["headers"]
    settings = await _configure(client, headers)
    tenant_id = settings["webhook_url"].rsplit("/", 1)[1]
    guest, _, _ = await _guest_with_order(client, headers, price=40)
    body = (await client.post("/api/v1/guest/payments/create", headers=guest)).json()
    fake_gateway.pay(body["provider_order_id"], 4000)

    entity = {"order_id": body["provider_order_id"]}
    payload = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": entity}}}).encode()
    url = f"/api/v1/webhooks/razorpay/{tenant_id}"

    bad = await client.post(url, content=payload, headers={"X-Razorpay-Signature": "nope"})
    assert bad.status_code == 400

    signature = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    ok = await client.post(url, content=payload, headers={"X-Razorpay-Signature": signature})
    assert ok.status_code == 200, ok.text

    status = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert status.json()["status"] == "paid"


async def test_online_payment_disabled_falls_back(client: AsyncClient, pro_max_tenant_admin: dict):
    headers = pro_max_tenant_admin["headers"]
    guest, _, _ = await _guest_with_order(client, headers, price=30)
    preview = await client.get("/api/v1/guest/bill-preview", headers=guest)
    assert preview.json()["online_payment"]["enabled"] is False
    create = await client.post("/api/v1/guest/payments/create", headers=guest)
    assert create.status_code == 400
