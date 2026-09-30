import uuid

from pydantic import BaseModel, Field


class OnlinePaymentSettingsResponse(BaseModel):
    """Never includes the secrets themselves — only whether they're set."""

    available: bool  # plan allows it (QR self-order is a Pro Max feature)
    enabled: bool
    provider: str
    auth_mode: str
    key_id: str | None
    has_secret: bool
    has_webhook_secret: bool
    is_test_mode: bool
    webhook_url: str


class OnlinePaymentSettingsRequest(BaseModel):
    # Omitted / blank secret fields leave the stored value untouched, so the owner can
    # change the enabled switch without re-typing keys.
    key_id: str | None = Field(default=None, max_length=100)
    key_secret: str | None = Field(default=None, max_length=200)
    webhook_secret: str | None = Field(default=None, max_length=200)
    enabled: bool | None = None


class OnlinePaymentTestResponse(BaseModel):
    ok: bool
    is_test_mode: bool


class GuestOnlinePaymentInfo(BaseModel):
    """What the guest Bill tab needs to decide between "Pay online" and the plain QR."""

    enabled: bool = False
    key_id: str | None = None
    is_test_mode: bool = False
    paid: bool = False
    paid_amount: float | None = None
    reference: str | None = None


class GuestCreatePaymentResponse(BaseModel):
    provider_order_id: str
    key_id: str
    amount_paise: int
    currency: str
    hotel_name: str
    description: str
    customer_name: str | None
    customer_phone: str | None
    is_test_mode: bool


class GuestPaymentStatusResponse(BaseModel):
    status: str  # none | created | paid | failed
    paid_amount: float | None = None
    reference: str | None = None
    failure_reason: str | None = None
    attempt_id: uuid.UUID | None = None
