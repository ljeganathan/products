import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.models.enums import SubscriptionStatus, UserRole
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.tenant_repository import TenantRepository
from app.schemas.common import PaginatedResponse
from app.schemas.platform_subscription import (
    ChangePlanRequest,
    SubscriptionCreate,
    SubscriptionOut,
    SubscriptionUpdate,
)
from app.services.subscription_service import BILLING_PERIOD_DAYS, get_plan_change_blockers

router = APIRouter(prefix="/platform/subscriptions", tags=["platform"])

require_owner = require_role(UserRole.PRODUCT_OWNER)


def _to_out(row: tuple[Subscription, Tenant, Plan, Plan | None]) -> SubscriptionOut:
    subscription, tenant, plan, requested_plan = row
    return SubscriptionOut(
        id=subscription.id,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        plan_id=plan.id,
        plan_code=plan.code,
        plan_name=plan.name,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        extra_users=subscription.extra_users,
        extra_stores=subscription.extra_stores,
        requested_plan_id=subscription.requested_plan_id,
        requested_plan_code=requested_plan.code if requested_plan else None,
        upgrade_requested_at=subscription.upgrade_requested_at,
    )


@router.get("", response_model=PaginatedResponse[SubscriptionOut])
async def list_subscriptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: uuid.UUID | None = Query(None),
    status_filter: SubscriptionStatus | None = Query(None, alias="status"),
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[SubscriptionOut]:
    rows, total = await SubscriptionRepository(db).list_all(
        page=page, page_size=page_size, tenant_id=tenant_id, status=status_filter
    )
    return PaginatedResponse(
        items=[_to_out(row) for row in rows], total=total, page=page, page_size=page_size
    )


@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    payload: SubscriptionCreate,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut:
    tenant = await TenantRepository(db).get_by_id(payload.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    plan = await PlanRepository(db).get_by_id(payload.plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    sub_repo = SubscriptionRepository(db)
    await sub_repo.cancel_active_for_tenant(payload.tenant_id)

    now = datetime.now(UTC)
    subscription = await sub_repo.create(
        Subscription(
            tenant_id=payload.tenant_id,
            plan_id=payload.plan_id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now,
            current_period_end=now + timedelta(days=BILLING_PERIOD_DAYS),
        )
    )
    await db.commit()
    row = await sub_repo.get_by_id_joined(subscription.id)
    assert row is not None
    return _to_out(row)


@router.patch("/{subscription_id}", response_model=SubscriptionOut)
async def update_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut:
    sub_repo = SubscriptionRepository(db)
    row = await sub_repo.get_by_id_joined(subscription_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")

    subscription = row[0]
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(subscription, field, value)

    await db.flush()
    await db.commit()
    row = await sub_repo.get_by_id_joined(subscription_id)
    assert row is not None
    return _to_out(row)


@router.patch("/{subscription_id}/change-plan", response_model=SubscriptionOut)
async def change_plan(
    subscription_id: uuid.UUID,
    payload: ChangePlanRequest,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut:
    sub_repo = SubscriptionRepository(db)
    row = await sub_repo.get_by_id_joined(subscription_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    subscription, tenant, _current_plan, _ = row

    target_plan = await PlanRepository(db).get_by_id(payload.plan_id)
    if target_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    blockers = await get_plan_change_blockers(db, tenant.id, subscription, target_plan)
    if blockers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot change plan: " + " ".join(blockers),
        )

    subscription.plan_id = target_plan.id
    # This change-plan action is exactly what resolves a pending tenant-side
    # upgrade request (api/v1/subscription.py), whether or not the applied
    # plan matches what was originally requested.
    subscription.requested_plan_id = None
    subscription.upgrade_requested_at = None
    await db.flush()
    await db.commit()

    row = await sub_repo.get_by_id_joined(subscription_id)
    assert row is not None
    return _to_out(row)
