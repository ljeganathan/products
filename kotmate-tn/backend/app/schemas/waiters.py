import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WaiterCreateRequest(BaseModel):
    location_id: uuid.UUID
    waiter_number: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = None
    # % on net sale value (post-discount, pre-tax) — CLAUDE.md §11.
    incentive_rate: float | None = Field(default=None, ge=0, le=100)
    # Optional link to a `waiter`-role login — POS (Phase 07) auto-locks that login's
    # waiter selector to this row. Omit to track a waiter without app access.
    user_id: uuid.UUID | None = None


class WaiterUpdateRequest(BaseModel):
    location_id: uuid.UUID | None = None
    waiter_number: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = None
    incentive_rate: float | None = Field(default=None, ge=0, le=100)
    user_id: uuid.UUID | None = None
    is_active: bool | None = None


class WaiterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location_id: uuid.UUID
    waiter_number: str
    name: str
    phone: str | None
    incentive_rate: float | None
    user_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
