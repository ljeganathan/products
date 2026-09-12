import uuid

from pydantic import BaseModel, Field

from app.schemas.bills import BillPreviewResponse
from app.schemas.orders import OrderLineInput


class GuestSessionResponse(BaseModel):
    """Returned by both the initial QR scan and the name/phone PATCH — the guest
    frontend's entire "am I logged in, and to what" state lives in this shape plus the
    token, nothing else. `location_id`/`table_id` are echoed here (not just left
    inside the JWT) so the frontend never has to decode a token just to get values it
    needs immediately, e.g. to open the location websocket. No customer/seat identity
    — one table's QR always means "the table's one shared order."

    For a Takeaway/non-seating session (Phase 26), `table_id`/`table_number` are null
    and `pickup_token`/`section_name_en` are set instead — the guest frontend shows the
    pickup token where it would otherwise show a table number (CLAUDE.md §9).
    """

    guest_token: str
    tenant_id: uuid.UUID
    location_id: uuid.UUID
    table_id: uuid.UUID | None
    table_number: str | None
    pickup_token: str | None = None
    section_name_en: str | None = None
    customer_name: str | None
    customer_phone: str | None
    order_id: uuid.UUID | None
    status: str


class GuestProfileUpdateRequest(BaseModel):
    """Always optional — CLAUDE.md's product framing is explicit that name/phone are
    never a precondition to ordering, just a nice-to-have for the tenant.
    """

    customer_name: str | None = Field(default=None, max_length=100)
    customer_phone: str | None = Field(default=None, max_length=20)


class GuestCartUpdateRequest(BaseModel):
    """Full cart replace, same contract as the staff `OrderUpdateRequest.items` — the
    guest frontend computes the next full line list client-side (merge into an
    existing unsent line vs. append a new one) exactly the way `usePosDraftOrder`
    already does, rather than this endpoint growing its own merge semantics.
    """

    items: list[OrderLineInput]


class GuestBillPreviewResponse(BillPreviewResponse):
    """Same shape `bill_service.preview_bill` already returns for the staff billing
    screen, plus the one thing only the guest side needs: a ready-to-tap UPI deep
    link. `None` when the location has no UPI id configured (Hotel Master) — the
    guest UI then just doesn't show the "Pay via UPI" button.
    """

    upi_link: str | None = None


class RequestBillResponse(BaseModel):
    status: str


class TableQrCodeResponse(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID
    table_number: str
    qr_token: str
    is_active: bool


class SectionQrCodeResponse(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    section_name_en: str
    qr_token: str
    is_active: bool


class QrSelfOrderSettingsRequest(BaseModel):
    enabled: bool


class QrSelfOrderSettingsResponse(BaseModel):
    enabled: bool
