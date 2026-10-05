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


async def test_takeaway_kot_fires_automatically_once_paid_online(
    client: AsyncClient, pro_max_tenant_admin: dict, fake_gateway
):
    """A takeaway order stays pending until paid; once the payment is verified its kitchen
    ticket fires by itself, and a second check does not send it again.
    """
    from tests.test_takeaway_qr_ordering import (
        _create_category as tw_category,
    )
    from tests.test_takeaway_qr_ordering import (
        _create_item as tw_item,
    )
    from tests.test_takeaway_qr_ordering import (
        _default_location_id as tw_location,
    )
    from tests.test_takeaway_qr_ordering import (
        _enable_qr_self_order as tw_enable,
    )
    from tests.test_takeaway_qr_ordering import (
        _generate_section_qr,
    )
    from tests.test_takeaway_qr_ordering import (
        _guest_headers as tw_guest,
    )
    from tests.test_takeaway_qr_ordering import (
        _section_id as tw_section,
    )
    from tests.test_takeaway_qr_ordering import (
        _set_guest_profile as tw_profile,
    )
    from tests.test_takeaway_qr_ordering import (
        _start_guest_session as tw_start,
    )

    headers = pro_max_tenant_admin["headers"]
    await _configure(client, headers)
    await tw_enable(client, headers)
    location_id = await tw_location(client, headers)
    section_id = await tw_section(client, headers, "Takeaway")
    qr_token = await _generate_section_qr(client, headers, section_id, location_id)
    category = await tw_category(client, headers)
    item = await tw_item(client, headers, category["id"], price=60)

    guest = tw_guest(await tw_start(client, qr_token))
    await tw_profile(client, guest)
    cart = await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )
    order_id = cart.json()["id"]
    created = (await client.post("/api/v1/guest/payments/create", headers=guest)).json()

    # Before payment the order shows to staff only as a pending row, never a real ticket.
    before = await client.get("/api/v1/kot/tickets/active", headers=headers)
    assert [t["status"] for t in before.json() if t["order_id"] == order_id] == ["pending"]

    fake_gateway.pay(created["provider_order_id"], 6000)
    paid = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert paid.json()["status"] == "paid"

    after = await client.get("/api/v1/kot/tickets/active", headers=headers)
    tickets = [t for t in after.json() if t["order_id"] == order_id]
    assert [t["status"] for t in tickets] == ["new"]

    # Checking again must not fire a second ticket for the same items.
    await client.get("/api/v1/guest/payments/status", headers=guest)
    again = await client.get("/api/v1/kot/tickets/active", headers=headers)
    assert len([t for t in again.json() if t["order_id"] == order_id]) == 1


async def test_dine_in_send_to_kitchen_prints_on_network_kot_printer(
    client: AsyncClient, pro_max_tenant_admin: dict, monkeypatch
):
    """Tapping "Send to Kitchen" on a table QR fires the KOT and sends it straight to a
    network kitchen printer, with no printer setup on the customer's side.
    """
    from app.services import kot_service
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

    sent: list[tuple] = []

    def fake_send(ip, port, content):
        sent.append((ip, port, content))
        return None

    monkeypatch.setattr(kot_service, "send_raw_bytes_over_network", fake_send)

    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_qr(client, headers, table["id"])
    printer = await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Kitchen",
            "target": "kot",
            "printer_type": "thermal",
            "connection_type": "network",
            "connection_details": {"ip_address": "192.168.0.50", "port": 9100},
            "paper_width_mm": 80,
        },
        headers=headers,
    )
    assert printer.status_code == 201, printer.text

    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=40)
    guest = _guest_headers(await _start_guest_session(client, qr_token))
    await _set_guest_profile(client, guest)
    await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )

    send = await client.post("/api/v1/guest/send-kot", headers=guest)
    assert send.status_code == 201, send.text
    assert len(sent) == 1 and sent[0][0] == "192.168.0.50" and sent[0][1] == 9100
    assert len(sent[0][2]) > 0


async def test_bluetooth_kitchen_ticket_is_broadcast_with_print_job(
    client: AsyncClient, pro_max_tenant_admin: dict, monkeypatch
):
    """A Bluetooth (device-paired) kitchen printer can't be reached by the server, so a dine-in
    ticket must reach the open Kitchen Display with its print data attached, to print there.
    """
    from app.api.v1 import guest as guest_routes
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

    messages: list[dict] = []

    async def capture(location_id, message):
        messages.append(message)

    monkeypatch.setattr(guest_routes.ws_manager, "broadcast", capture)

    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    table = await _create_table(client, headers, location_id, section_id)
    await _enable_qr_self_order(client, headers)
    qr_token = await _generate_qr(client, headers, table["id"])
    printer = await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Kitchen BT",
            "target": "kot",
            "printer_type": "thermal",
            "connection_type": "bluetooth",
            "connection_details": {"device_name": "RP-80", "device_id": "abc"},
            "paper_width_mm": 80,
        },
        headers=headers,
    )
    assert printer.status_code == 201, printer.text

    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=40)
    guest = _guest_headers(await _start_guest_session(client, qr_token))
    await _set_guest_profile(client, guest)
    await client.post(
        "/api/v1/guest/cart", json={"items": [{"item_id": item["id"], "quantity": 1}]}, headers=guest
    )
    send = await client.post("/api/v1/guest/send-kot", headers=guest)
    assert send.status_code == 201, send.text

    kot = [m for m in messages if m.get("type") == "kot_ticket"]
    assert len(kot) == 1
    job = kot[0]["print_job"]
    assert job is not None and job["connection_type"] == "bluetooth" and job["data_base64"]
