import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import PlanCode, SubscriptionStatus, TenantStatus
from app.schemas.common import UsageOut


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    owner_email: EmailStr
    owner_phone: str
    status: TenantStatus
    created_at: datetime
    subscription_id: uuid.UUID
    plan_id: uuid.UUID
    plan_code: PlanCode
    plan_name: str
    subscription_status: SubscriptionStatus
    current_period_end: datetime
    usage: UsageOut
    has_pending_upgrade_request: bool


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    owner_email: EmailStr
    owner_phone: str = Field(min_length=1, max_length=20)
    plan_code: PlanCode
    store_name: str | None = None
    admin_name: str = Field(min_length=1, max_length=150)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=72)


class TenantUpdate(BaseModel):
    status: TenantStatus
