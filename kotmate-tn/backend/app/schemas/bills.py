import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import DISCOUNT_TYPES, PAYMENT_METHODS


class BillDiscountInput(BaseModel):
    """One of the three tiers CLAUDE.md §6 gates by plan (`flat_percent` all tiers,
    `item_level` Pro+, `coupon` Pro Max) — which types are actually accepted for a given
    tenant is enforced in `bill_service`, not here, since it depends on the tenant's
    active plan rather than anything the request itself carries.
    """

    type: str
    # flat_percent / coupon: percentage off the subtotal.
    percent: float | None = Field(default=None, ge=0, le=100)
    coupon_code: str | None = None
    # item_level: order_item_id (as string) -> flat rupee amount off that line, capped
    # to the line's own total by the service.
    item_amounts: dict[str, float] | None = None

    @field_validator("type")
    @classmethod
    def _type_valid(cls, v: str) -> str:
        if v not in DISCOUNT_TYPES:
            raise ValueError(f"type must be one of {DISCOUNT_TYPES}")
        return v

    @model_validator(mode="after")
    def _shape_matches_type(self) -> "BillDiscountInput":
        if self.type == "flat_percent" and self.percent is None:
            raise ValueError("percent is required for type=flat_percent")
        if self.type == "coupon" and not self.coupon_code:
            raise ValueError("coupon_code is required for type=coupon")
        if self.type == "item_level" and not self.item_amounts:
            raise ValueError("item_amounts is required for type=item_level")
        return self


class BillPaymentInput(BaseModel):
    method: str
    amount: float = Field(gt=0)

    @field_validator("method")
    @classmethod
    def _method_valid(cls, v: str) -> str:
        if v not in PAYMENT_METHODS:
            raise ValueError(f"method must be one of {PAYMENT_METHODS}")
        return v


class BillCreateRequest(BaseModel):
    order_id: uuid.UUID
    discount: BillDiscountInput | None = None
    payments: list[BillPaymentInput] = Field(min_length=1)
    # order_item_id (string) -> tax_rule_id — Pro Max only ("multi_rate_per_item"),
    # rejected by the service on any other tax_mode. Anything above the audit threshold
    # is logged to audit_log (CLAUDE.md §11).
    line_tax_overrides: dict[str, uuid.UUID] | None = None


class BillPreviewRequest(BaseModel):
    """Same shape as `BillCreateRequest` but payments are optional — the frontend can
    ask "what would this bill total?" before the cashier has settled on a payment split.
    """

    order_id: uuid.UUID
    discount: BillDiscountInput | None = None
    line_tax_overrides: dict[str, uuid.UUID] | None = None


class BillItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    item_id: uuid.UUID
    name_en: str
    name_ta: str | None
    unit_price: float
    quantity: int
    line_total: float


class PaymentResponse(BaseModel):
    method: str
    amount: float


class BillTotals(BaseModel):
    items: list[BillItemResponse]
    subtotal: float
    discount_amount: float
    cgst_amount: float
    sgst_amount: float
    round_off_amount: float
    grand_total: float
    waiter_incentive_amount: float | None
    cashier_incentive_amount: float | None


class BillPreviewResponse(BillTotals):
    order_id: uuid.UUID
    payments: list[PaymentResponse] = Field(default_factory=list)


class BillResponse(BillTotals):
    id: uuid.UUID
    bill_number: str
    order_id: uuid.UUID
    location_id: uuid.UUID
    table_id: uuid.UUID | None
    table_number: str | None
    section_id: uuid.UUID
    section_name_en: str
    waiter_id: uuid.UUID | None
    waiter_name: str | None
    pos_user_id: uuid.UUID
    pos_user_login_id: str
    status: str
    payments: list[PaymentResponse]
    printed: bool
    created_at: datetime


class BillSearchParams(BaseModel):
    """Query params for `GET /api/v1/bills` — CLAUDE.md Phase 09 scope: "Old bill search
    (by bill number, date, table, waiter)".
    """

    bill_number: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    table_id: uuid.UUID | None = None
    waiter_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
