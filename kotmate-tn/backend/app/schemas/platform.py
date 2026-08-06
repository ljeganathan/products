import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import BILLING_CYCLES, INDIAN_STATES, PLAN_CODES, SUBSCRIPTION_STATUSES

_PINCODE_RE = r"^[1-9][0-9]{5}$"


class TenantCreateRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    door_no: str | None = None
    street: str | None = None
    city: str | None = None
    district: str | None = None
    state: str
    pincode: str = Field(pattern=_PINCODE_RE)

    plan_code: str
    billing_cycle: str = "monthly"

    location_name: str = Field(min_length=2, max_length=200)

    # Local handle only — the API composes the real login id as {tenant_code}-{handle}.
    admin_local_handle: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    admin_name: str = Field(min_length=2, max_length=200)
    admin_password: str = Field(min_length=8)

    @field_validator("state")
    @classmethod
    def _state_valid(cls, v: str) -> str:
        if v not in INDIAN_STATES:
            raise ValueError(f"state must be one of {INDIAN_STATES}")
        return v

    @field_validator("plan_code")
    @classmethod
    def _plan_code_valid(cls, v: str) -> str:
        if v not in PLAN_CODES:
            raise ValueError(f"plan_code must be one of {PLAN_CODES}")
        return v

    @field_validator("billing_cycle")
    @classmethod
    def _billing_cycle_valid(cls, v: str) -> str:
        if v not in BILLING_CYCLES:
            raise ValueError(f"billing_cycle must be one of {BILLING_CYCLES}")
        return v


class ChangePlanRequest(BaseModel):
    plan_code: str
    billing_cycle: str = "monthly"

    @field_validator("plan_code")
    @classmethod
    def _plan_code_valid(cls, v: str) -> str:
        if v not in PLAN_CODES:
            raise ValueError(f"plan_code must be one of {PLAN_CODES}")
        return v

    @field_validator("billing_cycle")
    @classmethod
    def _billing_cycle_valid(cls, v: str) -> str:
        if v not in BILLING_CYCLES:
            raise ValueError(f"billing_cycle must be one of {BILLING_CYCLES}")
        return v


class SubscriptionStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _status_valid(cls, v: str) -> str:
        if v not in SUBSCRIPTION_STATUSES:
            raise ValueError(f"status must be one of {SUBSCRIPTION_STATUSES}")
        return v


class TenantUpdateRequest(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    door_no: str | None = None
    street: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = Field(default=None, pattern=_PINCODE_RE)
    is_active: bool | None = None

    @field_validator("state")
    @classmethod
    def _state_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in INDIAN_STATES:
            raise ValueError(f"state must be one of {INDIAN_STATES}")
        return v


class TenantSummary(BaseModel):
    id: uuid.UUID
    tenant_code: str
    company_name: str
    is_active: bool
    plan_code: str | None
    subscription_status: str | None
    billing_cycle: str | None
    active_user_count: int
    max_users: int | None
    active_location_count: int
    max_locations: int | None
    admin_login_id: str | None


class TenantDetail(TenantSummary):
    door_no: str | None
    street: str | None
    city: str | None
    district: str | None
    state: str | None
    pincode: str | None
    current_period_start: date | None
    current_period_end: date | None
    created_at: datetime


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    max_users: int | None
    max_locations: int
    price_monthly: float
    price_yearly: float
    features: dict
    is_active: bool


class PlanUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=50)
    max_users: int | None = Field(default=None, ge=0)
    max_locations: int | None = Field(default=None, ge=1)
    price_monthly: float | None = Field(default=None, ge=0)
    price_yearly: float | None = Field(default=None, ge=0)
    features: dict | None = None
    is_active: bool | None = None


class MaintenanceSettingsUpdate(BaseModel):
    maintenance_mode: bool | None = None
    maintenance_message: str | None = None
    announcement_is_active: bool | None = None
    announcement_message: str | None = None


class MaintenanceSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    maintenance_mode: bool
    maintenance_message: str | None
    announcement_is_active: bool
    announcement_message: str | None


class PlatformMetrics(BaseModel):
    active_tenant_count: int
    mrr_estimate: float
    total_active_users: int
    total_max_users: int | None
    total_active_locations: int
    total_max_locations: int
