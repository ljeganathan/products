import uuid

from pydantic import BaseModel, Field


class ProviderStatus(BaseModel):
    """One card on the Settings screen. Never includes the secrets themselves."""

    provider: str  # razorpay | cashfree
    configured: bool  # key id and secret are saved
    enabled: bool  # this is the provider taking online payments right now
    key_id: str | None
    has_secret: bool
    has_webhook_secret: bool
    environment: str | None  # cashfree: sandbox | production; None for razorpay
    is_test_mode: bool
    webhook_url: str


class OnlinePaymentSettingsResponse(BaseModel):
    """Never includes the secrets themselves — only whether they're set.

    The top-level fields describe the provider that is currently enabled (or Razorpay when
    none is), so existing callers keep working. `providers` has one entry per provider.
    """

    available: bool  # plan allows it (QR self-order is a Pro Max feature)
    enabled: bool
    provider: str
    auth_mode: str
    key_id: str | None
    has_secret: bool
    has_webhook_secret: bool
    is_test_mode: bool
    webhook_url: str
    providers: list[ProviderStatus] = []


class OnlinePaymentSettingsRequest(BaseModel):
    # Which provider's card the owner is editing. Omitted means Razorpay (older screens).
    provider: str | None = Field(default=None, max_length=20)
    # Omitted / blank secret fields leave the stored value untouched, so the owner can
    # change the enabled switch without re-typing keys.
    key_id: str | None = Field(default=None, max_length=100)
    key_secret: str | None = Field(default=None, max_length=200)
    webhook_secret: str | None = Field(default=None, max_length=200)
    # Cashfree only: 'sandbox' or 'production'.
    environment: str | None = Field(default=None, max_length=10)
    enabled: bool | None = None


class OnlinePaymentTestResponse(BaseModel):
    ok: bool
    is_test_mode: bool


class GuestOnlinePaymentInfo(BaseModel):
    """What the guest Bill tab needs to decide between "Pay online" and the plain QR."""

    enabled: bool = False
    provider: str | None = None
    key_id: str | None = None
    is_test_mode: bool = False
    paid: bool = False
    paid_amount: float | None = None
    reference: str | None = None


class GuestCreatePaymentResponse(BaseModel):
    provider: str = "razorpay"
    provider_order_id: str
    # Razorpay checkout needs key_id; Cashfree's checkout needs payment_session_id instead.
    key_id: str
    payment_session_id: str | None = None
    amount_paise: int
    currency: str
    hotel_name: str
    description: str
    customer_name: str | None
    customer_phone: str | None
    is_test_mode: bool
    # Cashfree only: 'sandbox' | 'production', so the guest page loads the matching SDK mode.
    environment: str | None = None


class GuestPaymentStatusResponse(BaseModel):
    status: str  # none | created | paid | failed
    paid_amount: float | None = None
    reference: str | None = None
    failure_reason: str | None = None
    attempt_id: uuid.UUID | None = None
