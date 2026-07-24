import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription_view import (
    AvailablePlanOut,
    TenantSubscriptionOut,
    UpgradeRequestCreate,
)
from app.services.subscription_service import get_tenant_usage

router = APIRouter(prefix="/settings/subscription", tags=["subscription"])

require_admin = require_role(UserRole.ADMIN)


async def _build_view(db: AsyncSession, tenant_id: uuid.UUID) -> TenantSubscriptionOut:
    joined = await SubscriptionRepository(db).get_active_joined_for_tenant(tenant_id)
    if joined is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No active subscription for this tenant",
        )
    subscription, _, plan, requested_plan = joined
    usage = await get_tenant_usage(db, tenant_id, subscription, plan)
    return TenantSubscriptionOut(
        plan_code=plan.code,
        plan_name=plan.name,
        price_paise=plan.price_paise,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        usage=usage,
        requested_plan_code=requested_plan.code if requested_plan else None,
        requested_plan_name=requested_plan.name if requested_plan else None,
        upgrade_requested_at=subscription.upgrade_requested_at,
    )


@router.get("", response_model=TenantSubscriptionOut)
async def get_subscription(
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantSubscriptionOut:
    assert current_user.tenant_id is not None
    return await _build_view(db, current_user.tenant_id)


@router.get("/available-plans", response_model=list[AvailablePlanOut])
async def list_available_plans(
    current_user: CurrentUser = Depends(require_admin),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> list[AvailablePlanOut]:
    plans = await PlanRepository(db).list_all()
    return [
        AvailablePlanOut(id=p.id, code=p.code, name=p.name, price_paise=p.price_paise)
        for p in plans
        if p.is_active
    ]


@router.post(
    "/upgrade-request", response_model=TenantSubscriptionOut, status_code=status.HTTP_201_CREATED
)
async def request_upgrade(
    payload: UpgradeRequestCreate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantSubscriptionOut:
    assert current_user.tenant_id is not None

    target_plan = await PlanRepository(db).get_by_id(payload.plan_id)
    if target_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    subscription = await SubscriptionRepository(db).get_active_for_tenant(current_user.tenant_id)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No active subscription for this tenant",
        )

    subscription.requested_plan_id = target_plan.id
    subscription.upgrade_requested_at = datetime.now(UTC)
    await db.flush()
    result = await _build_view(db, current_user.tenant_id)
    await db.commit()
    return result
