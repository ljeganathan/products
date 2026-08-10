import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.constants import INDIAN_STATES

_PINCODE_RE = r"^[1-9][0-9]{5}$"
_GSTIN_RE = r"^[0-9]{2}[A-Z0-9]{13}$"


class HotelMasterUpdateRequest(BaseModel):
    """Upsert body — `PUT /api/v1/settings/hotel-master` creates the tenant_location's
    one-and-only hotel_master row on first save and updates it thereafter, so the
    frontend never needs to know whether one already exists (CLAUDE.md §10 Phase 10).
    """

    location_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    door_no: str | None = Field(default=None, max_length=50)
    street: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = None
    pincode: str | None = Field(default=None, pattern=_PINCODE_RE)
    phone: str | None = Field(default=None, max_length=20)
    gstin: str | None = Field(default=None, pattern=_GSTIN_RE)
    upi_id: str | None = Field(default=None, max_length=100)
    show_tamil_names: bool = True
    # Printed centered near the end of the bill (e.g. "Thank You & Visit Again..!!!").
    # None/omitted falls back to a generic default at print time (bill_service.py), not
    # here — this field only carries an explicit override.
    receipt_footer_message: str | None = Field(default=None, max_length=200)

    @field_validator("pincode", "gstin", "state", "receipt_footer_message", mode="before")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        # The settings form sends "" for an untouched optional field rather than
        # omitting the key — without this, "" would fail the pincode/GSTIN regex
        # pattern (which only skips validation for None, not empty string) or the
        # state-membership check below.
        return v or None

    @field_validator("state")
    @classmethod
    def _state_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in INDIAN_STATES:
            raise ValueError(f"state must be one of {INDIAN_STATES}")
        return v


class HotelMasterResponse(BaseModel):
    id: uuid.UUID | None = None
    location_id: uuid.UUID
    name: str | None = None
    door_no: str | None = None
    street: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None
    phone: str | None = None
    gstin: str | None = None
    logo_url: str | None = None
    upi_id: str | None = None
    show_tamil_names: bool = True
    receipt_footer_message: str | None = None
    # Non-blocking (CLAUDE.md Phase 10 acceptance criteria: "warn, don't hard-block") —
    # None when there's nothing to flag (no GSTIN, no state, or they already agree).
    gstin_state_warning: str | None = None
    created_at: datetime | None = None
