"""Cashfree as a second online payment provider, and the 'online' bill payment method.

Both gateways' HTTP layers are replaced with in-memory fakes (same approach as
test_online_payments.py), so these run offline and never touch Razorpay or Cashfree.
"""

import base64
import hashlib
import hmac
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db.session import async_session_maker
from app.models import Payment
from app.schemas.reports import PaymentMethodTotal
from app.services import payment_gateway
from app.services.payment_gateway import CashfreeGateway, RazorpayGateway
from app.services.report_print_service import _payment_pairs
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

RZP_KEY_ID = "rzp_test_abc123"
RZP_SECRET = "shhh-secret"
CF_CLIENT_ID = "CF_TEST_CLIENT"
CF_CLIENT_SECRET = "cf-secret-value"


class FakeCashfree:
    def __init__(self) -> None:
        self.payments: dict[str, list[dict]] = {}
        self.created: list[dict] = []
        self.check_code = 404  # 404 = keys accepted (made-up order not found)

    async def request(self, method: str, path: str, body: dict | None = None):
        if method == "POST" and path == "/orders":
            self.created.append(dict(body or {}))
            order_id = body["order_id"]
            self.payments[order_id] = []
            return {
                "order_id": order_id,
                "payment_session_id": f"session_{order_id}",
                "order_status": "ACTIVE",
            }
        if method == "GET" and path.startswith("/orders/") and path.endswith("/payments"):
            return self.payments.get(path.split("/")[2], [])
        raise AssertionError(f"unexpected Cashfree call {method} {path}")

    def pay(self, order_id: str, amount_rupees: float, status: str = "SUCCESS") -> str:
        cf_payment_id = f"cf_{uuid.uuid4().hex[:10]}"
        self.payments[order_id].append(
            {
                "cf_payment_id": cf_payment_id,
                "payment_status": status,
                "payment_amount": amount_rupees,
                "payment_group": "upi",
                "payment_message": None if status == "SUCCESS" else "Declined",
            }
        )
        return cf_payment_id


class FakeRazorpay:
    def __init__(self) -> None:
        self.payments: dict[str, list[dict]] = {}

    async def request(self, method: str, path: str, body: dict | None = None):
        if method == "POST" and path == "/orders":
            order_id = f"order_{uuid.uuid4().hex[:12]}"
            self.payments[order_id] = []
            return {"id": order_id, "amount": body["amount"], "status": "created"}
        if method == "GET" and path.endswith("/payments"):
            return {"items": self.payments.get(path.split("/")[2], [])}
        raise AssertionError(f"unexpected Razorpay call {method} {path}")

    def pay(self, order_id: str, amount_paise: int) -> str:
        pay_id = f"pay_{uuid.uuid4().hex[:10]}"
        self.payments[order_id].append(
            {
                "id": pay_id,
                "order_id": order_id,
                "amount": amount_paise,
                "status": "captured",
                "method": "upi",
            }
        )
        return pay_id


@pytest.fixture
def fakes(monkeypatch):
    cashfree, razorpay = FakeCashfree(), FakeRazorpay()

    async def cf_request(self, method, path, body=None):
        return await cashfree.request(method, path, body)

    def cf_request_sync(self, method, path, body=None):
        return cashfree.check_code, {}

    async def rzp_request(self, method, path, body=None):
        return await razorpay.request(method, path, body)

    monkeypatch.setattr(CashfreeGateway, "_request", cf_request)
    monkeypatch.setattr(CashfreeGateway, "_request_sync", cf_request_sync)
    monkeypatch.setattr(RazorpayGateway, "_request", rzp_request)
    return cashfree, razorpay


async def _save_provider(client: AsyncClient, headers: dict, provider: str, enabled: bool, **extra) -> dict:
    body = {"provider": provider, "enabled": enabled, **extra}
    if provider == "cashfree":
        body.setdefault("key_id", CF_CLIENT_ID)
        body.setdefault("key_secret", CF_CLIENT_SECRET)
        body.setdefault("environment", "sandbox")
    else:
        body.setdefault("key_id", RZP_KEY_ID)
        body.setdefault("key_secret", RZP_SECRET)
    resp = await client.put("/api/v1/settings/online-payments", json=body, headers=headers)
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
    return guest, cart.json()


async def test_settings_list_both_providers_and_only_one_enabled(
    client: AsyncClient, pro_max_tenant_admin: dict, fakes
):
    headers = pro_max_tenant_admin["headers"]
    await _save_provider(client, headers, "razorpay", enabled=True)
    body = await _save_provider(client, headers, "cashfree", enabled=True)

    by_name = {p["provider"]: p for p in body["providers"]}
    assert by_name["cashfree"]["enabled"] is True and by_name["cashfree"]["environment"] == "sandbox"
    assert by_name["razorpay"]["enabled"] is False  # switched off when Cashfree was switched on
    assert body["provider"] == "cashfree" and body["enabled"] is True
    assert by_name["cashfree"]["is_test_mode"] is True
    # Secrets never come back.
    assert CF_CLIENT_SECRET not in json.dumps(body) and RZP_SECRET not in json.dumps(body)

    switched = await _save_provider(client, headers, "razorpay", enabled=True)
    by_name = {p["provider"]: p for p in switched["providers"]}
    assert by_name["razorpay"]["enabled"] is True and by_name["cashfree"]["enabled"] is False
    assert switched["provider"] == "razorpay"


async def test_cashfree_needs_an_environment_before_it_can_be_enabled(
    client: AsyncClient, pro_max_tenant_admin: dict, fakes
):
    headers = pro_max_tenant_admin["headers"]
    resp = await client.put(
        "/api/v1/settings/online-payments",
        json={
            "provider": "cashfree",
            "key_id": CF_CLIENT_ID,
            "key_secret": CF_CLIENT_SECRET,
            "enabled": True,
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "Sandbox or Production" in resp.json()["detail"]


async def test_cashfree_connection_test_reports_bad_credentials(
    client: AsyncClient, pro_max_tenant_admin: dict, fakes, monkeypatch
):
    headers = pro_max_tenant_admin["headers"]
    await _save_provider(client, headers, "cashfree", enabled=False)
    ok = await client.post("/api/v1/settings/online-payments/test?provider=cashfree", headers=headers)
    assert ok.status_code == 200 and ok.json()["is_test_mode"] is True

    def rejected(self, method, path, body=None):
        return 401, {}

    monkeypatch.setattr(CashfreeGateway, "_request_sync", rejected)
    bad = await client.post("/api/v1/settings/online-payments/test?provider=cashfree", headers=headers)
    assert bad.status_code == 401
    assert "client ID or client secret" in bad.json()["detail"]


async def test_guest_pays_with_cashfree_and_staff_sees_verified_payment(
    client: AsyncClient, pro_max_tenant_admin: dict, fakes
):
    cashfree, _ = fakes
    headers = pro_max_tenant_admin["headers"]
    await _save_provider(client, headers, "cashfree", enabled=True)
    guest, order = await _guest_with_order(client, headers, price=100)

    preview = await client.get("/api/v1/guest/bill-preview", headers=guest)
    assert preview.json()["online_payment"]["provider"] == "cashfree"
    assert preview.json()["online_payment"]["key_id"] == CF_CLIENT_ID

    created = await client.post("/api/v1/guest/payments/create", headers=guest)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["provider"] == "cashfree"
    assert body["payment_session_id"] == f"session_{body['provider_order_id']}"
    assert body["environment"] == "sandbox" and body["is_test_mode"] is True
    # Amount comes from the server's bill, sent to Cashfree in rupees.
    assert cashfree.created[-1]["order_amount"] == "100.00"
    assert cashfree.created[-1]["customer_details"]["customer_phone"] == "9876543210"

    cashfree.pay(body["provider_order_id"], 60.00)  # wrong amount must not mark it paid
    assert (await client.get("/api/v1/guest/payments/status", headers=guest)).json()["status"] == "created"

    cf_id = cashfree.pay(body["provider_order_id"], 100.00)
    paid = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert paid.json()["status"] == "paid" and paid.json()["reference"] == cf_id

    staff_preview = await client.post(
        "/api/v1/bills/preview", json={"order_id": order["id"]}, headers=headers
    )
    assert staff_preview.json()["online_paid_amount"] == 100
    assert staff_preview.json()["online_payment_reference"] == cf_id


async def test_cashfree_webhook_requires_valid_signature_and_marks_paid(
    client: AsyncClient, pro_max_tenant_admin: dict, fakes
):
    cashfree, _ = fakes
    headers = pro_max_tenant_admin["headers"]
    settings = await _save_provider(client, headers, "cashfree", enabled=True)
    cashfree_card = next(p for p in settings["providers"] if p["provider"] == "cashfree")
    tenant_id = cashfree_card["webhook_url"].rsplit("/", 1)[1]
    guest, _ = await _guest_with_order(client, headers, price=40)
    body = (await client.post("/api/v1/guest/payments/create", headers=guest)).json()
    cf_id = cashfree.pay(body["provider_order_id"], 40.00)

    payload = json.dumps(
        {"type": "PAYMENT_SUCCESS_WEBHOOK", "data": {"order": {"order_id": body["provider_order_id"]}}}
    ).encode()
    timestamp = "1760000000"
    url = f"/api/v1/webhooks/cashfree/{tenant_id}"

    bad = await client.post(
        url, content=payload, headers={"x-webhook-timestamp": timestamp, "x-webhook-signature": "nope"}
    )
    assert bad.status_code == 400

    digest = hmac.new(CF_CLIENT_SECRET.encode(), timestamp.encode() + payload, hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode("ascii")
    ok = await client.post(
        url, content=payload, headers={"x-webhook-timestamp": timestamp, "x-webhook-signature": signature}
    )
    assert ok.status_code == 200, ok.text
    status = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert status.json()["status"] == "paid" and status.json()["reference"] == cf_id


async def test_payment_in_flight_still_settles_after_switching_provider(
    client: AsyncClient, pro_max_tenant_admin: dict, fakes
):
    _, razorpay = fakes
    headers = pro_max_tenant_admin["headers"]
    await _save_provider(client, headers, "razorpay", enabled=True)
    guest, _ = await _guest_with_order(client, headers, price=70)
    created = (await client.post("/api/v1/guest/payments/create", headers=guest)).json()
    assert created["provider"] == "razorpay"

    # The owner switches to Cashfree while the guest is still in the UPI app.
    await _save_provider(client, headers, "cashfree", enabled=True)
    pay_id = razorpay.pay(created["provider_order_id"], 7000)
    paid = await client.get("/api/v1/guest/payments/status", headers=guest)
    assert paid.json()["status"] == "paid" and paid.json()["reference"] == pay_id


async def test_online_method_on_bill_carries_gateway_reference(
    client: AsyncClient, pro_max_tenant_admin: dict, fakes
):
    cashfree, _ = fakes
    headers = pro_max_tenant_admin["headers"]
    await _save_provider(client, headers, "cashfree", enabled=True)
    guest, order = await _guest_with_order(client, headers, price=100)
    created = (await client.post("/api/v1/guest/payments/create", headers=guest)).json()
    cf_id = cashfree.pay(created["provider_order_id"], 100.00)
    await client.get("/api/v1/guest/payments/status", headers=guest)

    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "online", "amount": 100}]},
        headers=headers,
    )
    assert bill.status_code == 201, bill.text
    assert bill.json()["payments"][0]["method"] == "online"
    # The bill response doesn't expose the gateway reference, so read the stored line.
    async with async_session_maker() as session:
        await session.execute(text("SELECT set_config('app.is_platform_admin', 'true', true)"))
        line = (
            await session.execute(select(Payment).where(Payment.bill_id == uuid.UUID(bill.json()["id"])))
        ).scalar_one()
    assert line.method == "online" and line.reference == cf_id


async def test_counter_online_payment_and_default_method_accept_online(
    client: AsyncClient, pro_max_tenant_admin: dict, fakes
):
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "Takeaway")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=55)
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

    default = await client.patch(
        "/api/v1/settings/default-payment-method", json={"default_payment_method": "online"}, headers=headers
    )
    assert default.status_code == 200, default.text
    await client.patch(
        "/api/v1/settings/default-payment-method", json={"default_payment_method": "cash"}, headers=headers
    )

    bad = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "wallet", "amount": 55}]},
        headers=headers,
    )
    assert bad.status_code == 422

    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "online", "amount": 55}]},
        headers=headers,
    )
    assert bill.status_code == 201, bill.text
    assert bill.json()["payments"][0]["method"] == "online"


def test_online_row_only_printed_when_the_period_has_online_payments():
    cash_only = [PaymentMethodTotal(method="cash", amount=100.0)]
    labels = [label for label, _ in _payment_pairs(cash_only)]
    assert "Payment - Online" not in labels
    assert labels == ["Payment - Cash", "Payment - UPI", "Payment - Card"]

    with_online = cash_only + [PaymentMethodTotal(method="online", amount=250.5)]
    pairs = dict(_payment_pairs(with_online))
    assert pairs["Payment - Online"] == "250.50"


def test_provider_order_and_defaults_are_stable():
    assert payment_gateway.PROVIDERS == ("razorpay", "cashfree")
    assert payment_gateway.to_paise(10.005) == 1001
