import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import INCENTIVE_ELIGIBLE_ROLE_CODES, TENANT_STAFF_ROLE_CODES

_LOCAL_HANDLE_RE = r"^[A-Za-z0-9_-]+$"


class UserCreateRequest(BaseModel):
    # Local handle only — the API composes the real login id as {tenant_code}{handle}
    # (no separator, CLAUDE.md §5), same convention as tenant onboarding (Phase 03).
    local_handle: str = Field(min_length=2, max_length=50, pattern=_LOCAL_HANDLE_RE)
    name: str = Field(min_length=2, max_length=200)
    phone: str | None = None
    role: str
    password: str = Field(min_length=8)
    # % on net sale value (post-discount, pre-tax) — only meaningful for roles that ring
    # up bills directly (pos_user/Cashier, pos_operator/POS Operator).
    incentive_rate: float | None = Field(default=None, ge=0, le=100)
    location_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def _role_valid(cls, v: str) -> str:
        if v not in TENANT_STAFF_ROLE_CODES:
            raise ValueError(f"role must be one of {TENANT_STAFF_ROLE_CODES}")
        return v

    @model_validator(mode="after")
    def _incentive_only_for_billing_roles(self) -> "UserCreateRequest":
        if self.incentive_rate is not None and self.role not in INCENTIVE_ELIGIBLE_ROLE_CODES:
            raise ValueError(f"incentive_rate can only be set for role in {INCENTIVE_ELIGIBLE_ROLE_CODES}")
        return self


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = None
    role: str | None = None
    incentive_rate: float | None = Field(default=None, ge=0, le=100)
    location_ids: list[uuid.UUID] | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def _role_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in TENANT_STAFF_ROLE_CODES:
            raise ValueError(f"role must be one of {TENANT_STAFF_ROLE_CODES}")
        return v


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    local_handle: str
    name: str
    phone: str | None
    role: str
    incentive_rate: float | None
    location_ids: list[uuid.UUID]
    is_active: bool
    created_at: datetime


class SeatUsage(BaseModel):
    active_billable_users: int
    max_users: int | None
