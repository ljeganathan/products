import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import ORDER_STATUSES

# "billed" is Phase 09-only (POST /api/v1/bills) — this endpoint never sets it.
EDITABLE_ORDER_STATUSES = [s for s in ORDER_STATUSES if s != "billed"]


class OrderLineInput(BaseModel):
    item_id: uuid.UUID
    quantity: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=300)


class OrderCreateRequest(BaseModel):
    location_id: uuid.UUID
    section_id: uuid.UUID
    table_id: uuid.UUID | None = None
    # Ignored server-side for a `waiter` login — auto-locked to their own linked Waiter
    # Master row instead (CLAUDE.md §11).
    waiter_id: uuid.UUID | None = None
    items: list[OrderLineInput] = Field(default_factory=list)
    hold_label: str | None = Field(default=None, max_length=100)


class OrderUpdateRequest(BaseModel):
    section_id: uuid.UUID | None = None
    table_id: uuid.UUID | None = None
    waiter_id: uuid.UUID | None = None
    # Omit to leave items untouched (e.g. a pure table/section change); provide to fully
    # replace the cart contents (existing lines not present are removed).
    items: list[OrderLineInput] | None = None
    hold_label: str | None = Field(default=None, max_length=100)
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _status_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in EDITABLE_ORDER_STATUSES:
            raise ValueError(f"status must be one of {EDITABLE_ORDER_STATUSES}")
        return v


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    item_id: uuid.UUID
    name_en: str
    name_ta: str | None
    item_code: str | None = None
    unit_price: float
    quantity: int
    notes: str | None
    is_kot_sent: bool
    line_total: float
    # Live signals from the item master (Phase 05) — lets the cart grey out an item that
    # went out of stock after it was added, without a second lookup (CLAUDE.md §11).
    track_inventory: bool = False
    available_qty: int | None = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    section_id: uuid.UUID
    section_name_en: str
    section_is_seating: bool
    table_id: uuid.UUID | None
    table_number: str | None
    waiter_id: uuid.UUID | None
    waiter_name: str | None
    pos_user_id: uuid.UUID
    pos_user_login_id: str
    status: str
    hold_label: str | None
    items: list[OrderItemResponse]
    subtotal: float
    waiter_incentive_amount: float | None
    cashier_incentive_amount: float | None
    created_at: datetime


class OrderPreviewResponse(BaseModel):
    """Returned for `PATCH /orders/{id}?dry_run=true` — the frontend shows this to the
    user as a "totals will change" confirmation before re-issuing with dry_run=false
    (CLAUDE.md §9/Phase 07 table/section-change re-resolution rule).
    """

    order: OrderResponse
    subtotal_changed: bool
