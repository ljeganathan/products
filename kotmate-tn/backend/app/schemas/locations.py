import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import INDIAN_STATES

_PINCODE_RE = r"^[1-9][0-9]{5}$"


class LocationOption(BaseModel):
    """Minimal location shape for pickers (user location access, waiter/table master,
    POS location switcher) — broadly readable by any tenant-scoped role.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class LocationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    door_no: str | None = Field(default=None, max_length=50)
    street: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = None
    pincode: str | None = Field(default=None, pattern=_PINCODE_RE)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("pincode", "state", mode="before")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        # The Settings form sends "" for an untouched optional field rather than
        # omitting the key — without this, "" would fail the pincode regex pattern
        # (which only skips validation for None, not empty string) or the
        # state-membership check below.
        return v or None

    @field_validator("state")
    @classmethod
    def _state_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in INDIAN_STATES:
            raise ValueError(f"state must be one of {INDIAN_STATES}")
        return v


class LocationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    door_no: str | None = Field(default=None, max_length=50)
    street: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = None
    pincode: str | None = Field(default=None, pattern=_PINCODE_RE)
    phone: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None

    @field_validator("pincode", "state", mode="before")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v or None

    @field_validator("state")
    @classmethod
    def _state_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in INDIAN_STATES:
            raise ValueError(f"state must be one of {INDIAN_STATES}")
        return v


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    door_no: str | None
    street: str | None
    city: str | None
    district: str | None
    state: str | None
    pincode: str | None
    phone: str | None
    is_active: bool
    created_at: datetime
