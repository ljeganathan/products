"""Payment gateway abstraction — the only module that talks to Razorpay or Cashfree.

Everything else (guest payment endpoints, webhooks, settings) works against the small
`PaymentGateway` interface, and credentials are resolved in exactly one place
(`build_gateway`). A tenant has one row per provider (`tenant_payment_gateways`), and at
most one of them is enabled at a time (`get_gateway`). Each provider's webhook checks its
own signature, and payments are always re-read from the gateway before being trusted.

  * Razorpay Partner program (each hotel a sub-merchant onboarded by KOTMate, no key
    pasting): add an `auth_mode == "partner_oauth"` branch in `build_gateway`.
  * Another provider: add a class implementing `PaymentGateway` and a branch in
    `build_gateway` keyed by `TenantPaymentGateway.provider`.

Uses the standard library HTTP client (in a worker thread) so no new dependency is
needed on the backend image.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
import uuid
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import decrypt_secret
from app.models import TenantPaymentGateway

PROVIDERS = ("razorpay", "cashfree")

_RAZORPAY_API = "https://api.razorpay.com/v1"
_CASHFREE_API = {
    "sandbox": "https://sandbox.cashfree.com/pg",
    "production": "https://api.cashfree.com/pg",
}
_CASHFREE_API_VERSION = "2023-08-01"
_TIMEOUT_SECONDS = 15


def to_paise(amount: float) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class PaymentGateway(Protocol):
    provider: str

    @property
    def checkout_key(self) -> str: ...

    @property
    def is_test_mode(self) -> bool: ...

    async def create_order(
        self,
        amount_paise: int,
        receipt: str,
        notes: dict[str, str],
        customer_name: str | None,
        customer_phone: str | None,
    ) -> dict[str, Any]:
        """Returns at least `id` (the provider's order id). Cashfree also returns
        `payment_session_id`, which the guest checkout needs."""
        ...

    async def fetch_order_payments(self, provider_order_id: str) -> list[dict[str, Any]]:
        """Payments for the order, normalised to: id, status (captured | authorized | failed |
        pending), amount (paise), method, error_description."""
        ...

    async def capture_payment(self, provider_payment_id: str, amount_paise: int) -> dict[str, Any]: ...

    async def check_credentials(self) -> None: ...

    def verify_webhook(self, body: bytes, headers: Mapping[str, str]) -> bool: ...

    def webhook_order_id(self, payload: dict[str, Any]) -> str | None: ...


def _http_json(request: urllib.request.Request, name: str) -> tuple[int, dict[str, Any]]:
    """Returns (status, body) for any HTTP answer; raises 502 only when the host is unreachable."""
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001 - the generic message is used instead
            body = {}
        return exc.code, body
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Couldn't reach {name} — try again") from exc


def _raise_for_gateway_answer(code: int, detail: str, name: str) -> None:
    if code >= 400:
        http_code = status.HTTP_401_UNAUTHORIZED if code == 401 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(http_code, f"{name}: {detail}")


class RazorpayGateway:
    provider = "razorpay"

    def __init__(
        self,
        *,
        key_id: str,
        auth_secret: str,
        webhook_secret: str | None,
        auth_mode: str = "api_keys",
    ) -> None:
        self._key_id = key_id
        self._auth_secret = auth_secret
        self._webhook_secret = webhook_secret
        self._auth_mode = auth_mode

    @property
    def checkout_key(self) -> str:
        return self._key_id

    @property
    def is_test_mode(self) -> bool:
        return self._key_id.startswith("rzp_test_")

    def _authorization(self) -> str:
        if self._auth_mode == "partner_oauth":
            return f"Bearer {self._auth_secret}"
        token = base64.b64encode(f"{self._key_id}:{self._auth_secret}".encode()).decode("ascii")
        return f"Basic {token}"

    def _request_sync(self, method: str, path: str, body: dict | None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(  # noqa: S310 - fixed https Razorpay host
            f"{_RAZORPAY_API}{path}",
            data=data,
            method=method,
            headers={"Authorization": self._authorization(), "Content-Type": "application/json"},
        )
        code, answer = _http_json(request, "Razorpay")
        if code >= 400:
            detail = (answer.get("error") or {}).get("description") or "Payment gateway rejected the request"
            _raise_for_gateway_answer(code, detail, "Razorpay")
        return answer

    async def _request(self, method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._request_sync, method, path, body)

    async def create_order(
        self,
        amount_paise: int,
        receipt: str,
        notes: dict[str, str],
        customer_name: str | None,
        customer_phone: str | None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/orders",
            {"amount": amount_paise, "currency": "INR", "receipt": receipt[:40], "notes": notes},
        )

    async def fetch_order_payments(self, provider_order_id: str) -> list[dict[str, Any]]:
        result = await self._request("GET", f"/orders/{provider_order_id}/payments")
        return list(result.get("items", []))

    async def capture_payment(self, provider_payment_id: str, amount_paise: int) -> dict[str, Any]:
        return await self._request(
            "POST", f"/payments/{provider_payment_id}/capture", {"amount": amount_paise, "currency": "INR"}
        )

    async def check_credentials(self) -> None:
        await self._request("GET", "/orders?count=1")

    def verify_webhook(self, body: bytes, headers: Mapping[str, str]) -> bool:
        signature = headers.get("x-razorpay-signature", "")
        if not self._webhook_secret or not signature:
            return False
        expected = hmac.new(self._webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def webhook_order_id(self, payload: dict[str, Any]) -> str | None:
        return payload.get("payload", {}).get("payment", {}).get("entity", {}).get("order_id")


_CASHFREE_STATUS = {"SUCCESS": "captured", "FAILED": "failed"}


class CashfreeGateway:
    provider = "cashfree"

    def __init__(self, *, client_id: str, client_secret: str, environment: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._environment = environment

    @property
    def checkout_key(self) -> str:
        return self._client_id

    @property
    def is_test_mode(self) -> bool:
        return self._environment == "sandbox"

    def _request_sync(self, method: str, path: str, body: dict | None) -> tuple[int, dict[str, Any]]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(  # noqa: S310 - fixed https Cashfree host
            f"{_CASHFREE_API[self._environment]}{path}",
            data=data,
            method=method,
            headers={
                "x-client-id": self._client_id,
                "x-client-secret": self._client_secret,
                "x-api-version": _CASHFREE_API_VERSION,
                "Content-Type": "application/json",
            },
        )
        return _http_json(request, "Cashfree")

    async def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        code, answer = await asyncio.to_thread(self._request_sync, method, path, body)
        if code >= 400:
            detail = answer.get("message") or "Payment gateway rejected the request"
            _raise_for_gateway_answer(code, detail, "Cashfree")
        return answer

    async def create_order(
        self,
        amount_paise: int,
        receipt: str,
        notes: dict[str, str],
        customer_name: str | None,
        customer_phone: str | None,
    ) -> dict[str, Any]:
        digits = "".join(ch for ch in (customer_phone or "") if ch.isdigit())[-10:]
        if len(digits) != 10:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "A 10-digit phone number is needed to pay online"
            )
        answer = await self._request(
            "POST",
            "/orders",
            {
                "order_id": receipt,
                "order_amount": f"{amount_paise / 100:.2f}",
                "order_currency": "INR",
                "order_note": notes.get("for", "")[:100],
                "customer_details": {
                    "customer_id": f"cust_{receipt}".replace("-", "_")[:50],
                    "customer_phone": digits,
                    "customer_name": (customer_name or "Guest")[:100],
                },
            },
        )
        return {"id": answer["order_id"], "payment_session_id": answer["payment_session_id"]}

    async def fetch_order_payments(self, provider_order_id: str) -> list[dict[str, Any]]:
        answer = await self._request("GET", f"/orders/{provider_order_id}/payments")
        items = answer if isinstance(answer, list) else answer.get("items", [])
        return [
            {
                "id": str(item.get("cf_payment_id")),
                "status": _CASHFREE_STATUS.get(item.get("payment_status", ""), "pending"),
                "amount": to_paise(float(item.get("payment_amount", 0))),
                "method": item.get("payment_group"),
                "error_description": item.get("payment_message"),
            }
            for item in items
        ]

    async def capture_payment(self, provider_payment_id: str, amount_paise: int) -> dict[str, Any]:
        # Cashfree settles successful UPI and card payments by itself, so there is nothing to capture.
        return {"status": "not_supported"}

    async def check_credentials(self) -> None:
        # A made-up order id: 404 means the keys were accepted, 401/403 means they weren't.
        code, _ = await asyncio.to_thread(self._request_sync, "GET", "/orders/KM-KEY-CHECK", None)
        if code in (401, 403):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Cashfree rejected the client ID or client secret"
            )
        if code >= 500:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Cashfree: try again in a moment")

    def verify_webhook(self, body: bytes, headers: Mapping[str, str]) -> bool:
        signature = headers.get("x-webhook-signature", "")
        timestamp = headers.get("x-webhook-timestamp", "")
        if not signature or not timestamp:
            return False
        digest = hmac.new(self._client_secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
        return hmac.compare_digest(base64.b64encode(digest).decode("ascii"), signature)

    def webhook_order_id(self, payload: dict[str, Any]) -> str | None:
        return payload.get("data", {}).get("order", {}).get("order_id")


async def get_gateway_rows(session: AsyncSession, tenant_id: uuid.UUID) -> list[TenantPaymentGateway]:
    return list(
        (
            await session.execute(
                select(TenantPaymentGateway).where(TenantPaymentGateway.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    )


async def get_gateway_row(
    session: AsyncSession, tenant_id: uuid.UUID, provider: str
) -> TenantPaymentGateway | None:
    return (
        await session.execute(
            select(TenantPaymentGateway).where(
                TenantPaymentGateway.tenant_id == tenant_id,
                TenantPaymentGateway.provider == provider,
            )
        )
    ).scalar_one_or_none()


def build_gateway(row: TenantPaymentGateway) -> PaymentGateway | None:
    """The single place stored credentials become a live gateway client."""
    secret = decrypt_secret(row.secret_encrypted)
    if not row.key_id or not secret:
        return None
    if row.provider == "razorpay":
        if row.auth_mode not in ("api_keys", "partner_oauth"):
            return None
        return RazorpayGateway(
            key_id=row.key_id,
            auth_secret=secret,
            webhook_secret=decrypt_secret(row.webhook_secret_encrypted),
            auth_mode=row.auth_mode,
        )
    if row.provider == "cashfree":
        if row.environment not in _CASHFREE_API:
            return None
        return CashfreeGateway(client_id=row.key_id, client_secret=secret, environment=row.environment)
    return None


async def get_gateway(session: AsyncSession, tenant_id: uuid.UUID) -> PaymentGateway | None:
    """The provider switched on for new payments, or None when online payment is off."""
    rows = await get_gateway_rows(session, tenant_id)
    enabled = next((row for row in rows if row.is_enabled), None)
    return build_gateway(enabled) if enabled else None


async def get_gateway_for_provider(
    session: AsyncSession, tenant_id: uuid.UUID, provider: str
) -> PaymentGateway | None:
    """Any configured provider, enabled or not. Used to settle payments already in flight
    and to verify webhooks, so switching providers never strands an open payment."""
    row = await get_gateway_row(session, tenant_id, provider)
    return build_gateway(row) if row else None
