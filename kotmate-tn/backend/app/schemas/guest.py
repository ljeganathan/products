import re
import uuid

from pydantic import BaseModel, Field, field_validator

from app.schemas.bills import BillPreviewResponse
from app.schemas.online_payments import GuestOnlinePaymentInfo
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
    # Company name + this location's own name (CLAUDE.md §4's Company/Location split) —
    # shown on the guest menu header so a customer knows which hotel/branch they're
    # ordering from, since the QR flow never asks them to pick one themselves.
    hotel_name: str
    branch_name: str
    table_id: uuid.UUID | None
    table_number: str | None
    pickup_token: str | None = None
    section_name_en: str | None = None
    customer_name: str | None
    customer_phone: str | None
    order_id: uuid.UUID | None
    status: str


class GuestProfileUpdateRequest(BaseModel):
    """A generic partial-update primitive — either field left `None` leaves it
    untouched — reused for two different call sites with different requirements
    layered on top of it: the QR ordering flow (Phase 27) requires *both* fields be
    set before `guest_service.update_cart` will let a session place its first order
    (enforced there, not here, since this schema itself has no way to see whether the
    *other* field is already set on the session), while the header button's follow-up
    "edit your details" sheet reuses this same endpoint purely optionally once that
    initial requirement has already been satisfied.
    """

    customer_name: str | None = Field(default=None, max_length=100)
    customer_phone: str | None = Field(default=None, max_length=20)

    @field_validator("customer_phone")
    @classmethod
    def _normalize_phone(cls, v: str | None) -> str | None:
        """Strips everything but digits and keeps the last 10 (absorbs a "+91"/"0"
        prefix a guest might type) — this is the one path a future customer-loyalty
        feature would key lookups off of (CLAUDE.md's phone-based identity, Phase 27),
        so it's normalized strictly here even though a staff-entered `bills.
        customer_phone` (bill_service.py) stays free-text/lenient for a walk-in
        landline number.
        """
        if v is None:
            return None
        digits = re.sub(r"\D", "", v)
        if len(digits) < 10:
            raise ValueError("Enter a valid 10-digit phone number")
        return digits[-10:]


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
    # Whether the hotel takes online (Razorpay) payments, and whether this order has
    # already been paid that way (Phase 28). Absent/disabled -> the guest UI falls back
    # to the plain UPI QR above.
    online_payment: GuestOnlinePaymentInfo = GuestOnlinePaymentInfo()


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
