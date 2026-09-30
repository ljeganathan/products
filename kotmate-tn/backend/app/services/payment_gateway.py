"""Payment gateway abstraction (Phase 28) — the only module that talks to Razorpay.

Everything else (guest payment endpoints, webhook, settings) works against the small
`PaymentGateway` interface, and credentials are resolved in exactly one place
(`get_gateway`). Two changes then stay local to this file:

  * Razorpay Partner program (each hotel a sub-merchant onboarded by KOTMate, no key
    pasting): add an `auth_mode == "partner_oauth"` branch in `get_gateway` that builds
    a `RazorpayGateway` with a bearer access token (`account_ref` is the sub-merchant
    account id). Nothing outside this file changes.
  * Another provider (PayU, Cashfree, ...): add a class implementing `PaymentGateway`
    and select it by `TenantPaymentGateway.provider`.

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
from typing import Any, Protocol

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import decrypt_secret
from app.models import TenantPaymentGateway

_RAZORPAY_API = "https://api.razorpay.com/v1"
_TIMEOUT_SECONDS = 15


class PaymentGateway(Protocol):
    provider: str

    @property
    def checkout_key(self) -> str: ...

    @property
    def is_test_mode(self) -> bool: ...

    async def create_order(
        self, amount_paise: int, receipt: str, notes: dict[str, str]
    ) -> dict[str, Any]: ...

    async def fetch_order_payments(self, provider_order_id: str) -> list[dict[str, Any]]: ...

    async def capture_payment(self, provider_payment_id: str, amount_paise: int) -> dict[str, Any]: ...

    async def check_credentials(self) -> None: ...

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool: ...


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
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = "Payment gateway rejected the request"
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("description") or detail
            except Exception:  # noqa: BLE001 - keep the generic message
                pass
            code = status.HTTP_401_UNAUTHORIZED if exc.code == 401 else status.HTTP_502_BAD_GATEWAY
            raise HTTPException(code, f"Razorpay: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't reach Razorpay — try again") from exc

    async def _request(self, method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._request_sync, method, path, body)

    async def create_order(self, amount_paise: int, receipt: str, notes: dict[str, str]) -> dict[str, Any]:
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

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        if not self._webhook_secret or not signature:
            return False
        expected = hmac.new(self._webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


async def get_gateway_row(session: AsyncSession, tenant_id: uuid.UUID) -> TenantPaymentGateway | None:
    return (
        await session.execute(
            select(TenantPaymentGateway).where(TenantPaymentGateway.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()


def build_gateway(row: TenantPaymentGateway) -> PaymentGateway | None:
    """The single place stored credentials become a live gateway client."""
    if row.provider != "razorpay" or not row.key_id:
        return None
    secret = decrypt_secret(row.secret_encrypted)
    if not secret:
        return None
    if row.auth_mode not in ("api_keys", "partner_oauth"):
        return None
    return RazorpayGateway(
        key_id=row.key_id,
        auth_secret=secret,
        webhook_secret=decrypt_secret(row.webhook_secret_encrypted),
        auth_mode=row.auth_mode,
    )


async def get_gateway(session: AsyncSession, tenant_id: uuid.UUID, *, require_enabled: bool = True):
    row = await get_gateway_row(session, tenant_id)
    if row is None or (require_enabled and not row.is_enabled):
        return None
    return build_gateway(row)
