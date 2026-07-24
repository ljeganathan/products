import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import PlanCode, SubscriptionStatus


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_name: str
    plan_id: uuid.UUID
    plan_code: PlanCode
    plan_name: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    extra_users: int
    extra_stores: int
    requested_plan_id: uuid.UUID | None
    requested_plan_code: PlanCode | None
    upgrade_requested_at: datetime | None


class SubscriptionCreate(BaseModel):
    tenant_id: uuid.UUID
    plan_id: uuid.UUID


class ChangePlanRequest(BaseModel):
    plan_id: uuid.UUID


class SubscriptionUpdate(BaseModel):
    extra_users: int | None = Field(default=None, ge=0)
    extra_stores: int | None = Field(default=None, ge=0)
