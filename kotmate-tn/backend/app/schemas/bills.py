import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import PAYMENT_METHODS
from app.schemas.printing import PrintJobPayload


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
    # Item-level and flat discounts auto-apply from currently-active discount_rules
    # (Phase 23) — the cashier's only discount input is an optional coupon code.
    coupon_code: str | None = None
    payments: list[BillPaymentInput] = Field(min_length=1)
    # order_item_id (string) -> tax_rule_id — Pro Max only ("multi_rate_per_item"),
    # rejected by the service on any other tax_mode. Anything above the audit threshold
    # is logged to audit_log (CLAUDE.md §11).
    line_tax_overrides: dict[str, uuid.UUID] | None = None
    # Optional print-preview flow (POS): finalize without dispatching to the printer,
    # so the cashier can preview totals first — the existing reprint endpoint is used
    # to actually print once they confirm. Default False preserves the one-call
    # finalize-and-print flow for every other caller.
    skip_print: bool = False


class BillPreviewRequest(BaseModel):
    """Same shape as `BillCreateRequest` but payments are optional — the frontend can
    ask "what would this bill total?" before the cashier has settled on a payment split.
    """

    order_id: uuid.UUID
    coupon_code: str | None = None
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
    # Human-readable breakdown of which discount rule(s) applied, e.g. "Festival Offer
    # (10%): -₹45.00; Coupon WELCOME10: -₹15.00" — None when no discount applied.
    discount_note: str | None = None
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
    party_label: str | None
    pos_user_id: uuid.UUID
    pos_user_login_id: str
    status: str
    payments: list[PaymentResponse]
    printed: bool
    print_job: PrintJobPayload | None = None
    # Set only for a "network"/"wifi" printer the backend tried and failed to reach —
    # a message safe to show the cashier directly (PrintersPage's Test Print button and
    # lib/printDispatch.ts's frontend-side failures use the same plain-message contract).
    print_error: str | None = None
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
    # Phase 17: seating section (AC/Non-AC/...) and cashier-of-record filters — both
    # already snapshotted onto every bill, just weren't exposed as search params.
    section_id: uuid.UUID | None = None
    pos_user_id: uuid.UUID | None = None
