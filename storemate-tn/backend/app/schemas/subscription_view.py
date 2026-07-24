import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import PlanCode, SubscriptionStatus
from app.schemas.common import UsageOut


class TenantSubscriptionOut(BaseModel):
    plan_code: PlanCode
    plan_name: str
    price_paise: int
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    usage: UsageOut
    requested_plan_code: PlanCode | None
    requested_plan_name: str | None
    upgrade_requested_at: datetime | None


class UpgradeRequestCreate(BaseModel):
    plan_id: uuid.UUID


class AvailablePlanOut(BaseModel):
    """Minimal plan shape a tenant admin needs to pick an upgrade target —
    intentionally not the full `PlanOut` (limits/features_json are
    platform-console-only detail)."""

    id: uuid.UUID
    code: PlanCode
    name: str
    price_paise: int
