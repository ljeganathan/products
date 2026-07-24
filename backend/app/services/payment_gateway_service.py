"""Payment gateway extension point (Phase 7, v1 = manual/offline payment only).

StoreMate TN's v1 billing flow is entirely manual: the product owner console
generates a `subscription_invoices` row (see `subscription_service.
generate_next_invoice`) and marks it paid once payment is received offline
(bank transfer, UPI collect outside the app, cash, etc. — see
`api/v1/platform_invoices.py`). No gateway is called anywhere in that path
today, and `subscriptions.razorpay_subscription_id` stays `None` for every
tenant until a real integration lands.

This class is the documented seam for that later integration. Razorpay is
recommended (strong UPI support, an Indian entity, and a subscriptions API
that maps directly onto this schema) but the interface itself is
provider-neutral so swapping providers later only means a new subclass, not
a schema or call-site change.

Implementing `RazorpayGatewayService` means, at minimum:
  - `create_subscription`: call Razorpay's Subscriptions API with the plan's
    `price_paise`, store the returned id on `subscriptions.
    razorpay_subscription_id`.
  - `verify_webhook`: validate the `X-Razorpay-Signature` header (HMAC-SHA256
    over the raw body with the webhook secret) before trusting any event —
    Razorpay webhooks are the source of truth for `subscription.charged`,
    `subscription.cancelled`, `invoice.paid`, etc. in a v2 auto-billing flow.
  - `cancel`: call Razorpay's cancel endpoint, then reconcile local
    `subscriptions.status`.

Until that subclass exists, do not wire this interface into any router —
a stub that returns fake "success" would silently misrepresent real payment
state, which is worse than not having the feature at all.
"""

from abc import ABC, abstractmethod
from typing import Any


class PaymentGatewayService(ABC):
    @abstractmethod
    async def create_subscription(
        self, *, tenant_id: str, plan_code: str, price_paise: int
    ) -> str:
        """Create the subscription on the gateway side and return its
        provider-assigned subscription id (to store as
        `subscriptions.razorpay_subscription_id` or equivalent)."""
        raise NotImplementedError

    @abstractmethod
    async def verify_webhook(self, *, payload: bytes, signature: str) -> dict[str, Any]:
        """Verify the webhook's signature and return the parsed event body.
        Must raise if the signature is invalid — callers trust the return
        value implicitly."""
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, *, gateway_subscription_id: str) -> None:
        """Cancel the subscription on the gateway side."""
        raise NotImplementedError
