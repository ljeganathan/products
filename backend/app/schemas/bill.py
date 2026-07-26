import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BillStatus, DiscountType, PaymentMode
from app.schemas.company_settings import CompanySettingsOut


class BillItemCreate(BaseModel):
    item_id: uuid.UUID
    qty: float = Field(gt=0)
    discount_type: DiscountType | None = None
    # paise for flat, basis points for percent (10.50% -> 1050) — same
    # convention as discount_rules.value (CLAUDE.md's no-float-money rule).
    discount_value: int | None = Field(default=None, ge=0)


class BillCreate(BaseModel):
    store_id: uuid.UUID | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    payment_mode: PaymentMode
    items: list[BillItemCreate] = Field(min_length=1)
    bill_discount_type: DiscountType | None = None
    bill_discount_value: int | None = Field(default=None, ge=0)
    hold: bool = False


class BillItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    item_name_snapshot: str
    item_name_ta_snapshot: str | None
    qty: float
    unit_price_paise: int
    discount_paise: int
    tax_profile_snapshot_json: dict
    line_total_paise: int


class BillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    bill_number: int
    cashier_id: uuid.UUID
    customer_name: str | None
    customer_phone: str | None
    subtotal_paise: int
    discount_paise: int
    cgst_paise: int
    sgst_paise: int
    round_off_paise: int
    total_paise: int
    payment_mode: PaymentMode
    status: BillStatus
    printed_count: int
    created_at: datetime
    items: list[BillItemOut] = []


class BillSearchResponse(BaseModel):
    items: list[BillOut]
    total: int
    page: int
    page_size: int
    # Lets the frontend show an upgrade CTA instead of silently returning an
    # incomplete result set (Lite=7 / Pro=90 / Pro Max=-1 unlimited days).
    saved_bill_days: int
    window_start: date | None
    requested_from_clamped: bool


class ResumeBillResponse(BaseModel):
    """What the frontend reloads into the POS cart when recalling a held
    bill. The held bill row is deleted server-side once resumed — see
    services/billing_service.py::resume_held_bill."""

    store_id: uuid.UUID
    customer_name: str | None
    customer_phone: str | None
    payment_mode: PaymentMode
    items: list[BillItemCreate]


class PrintPayloadItem(BaseModel):
    name: str
    name_ta: str | None
    qty: float
    unit_price_paise: int
    discount_paise: int
    line_total_paise: int


class BillPrintPayload(BaseModel):
    bill_number: int
    created_at: datetime
    cashier_name: str
    customer_name: str | None
    customer_phone: str | None
    company: CompanySettingsOut
    items: list[PrintPayloadItem]
    subtotal_paise: int
    discount_paise: int
    cgst_paise: int
    sgst_paise: int
    round_off_paise: int
    total_paise: int
    payment_mode: PaymentMode
