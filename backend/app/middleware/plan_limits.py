import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SubscriptionStatus
from app.models.plan import Plan
from app.models.printer_profile import PrinterProfile
from app.models.store import Store
from app.models.subscription import Subscription
from app.models.user import User

UNLIMITED = -1


async def get_active_subscription_with_plan(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[Subscription, Plan]:
    result = await db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(
            Subscription.tenant_id == tenant_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .order_by(Subscription.created_at.desc())
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No active subscription for this tenant",
        )
    subscription, plan = row
    return subscription, plan


async def check_user_limit(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    subscription, plan = await get_active_subscription_with_plan(db, tenant_id)
    if plan.max_users == UNLIMITED:
        return

    limit = plan.max_users + subscription.extra_users
    count = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True))
    )
    if (count or 0) >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"User limit reached for the '{plan.name}' plan ({limit} users). "
                "Upgrade your plan or deactivate an existing user to add more."
            ),
        )


async def check_store_limit(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    subscription, plan = await get_active_subscription_with_plan(db, tenant_id)
    if plan.max_stores == UNLIMITED:
        return

    limit = plan.max_stores + subscription.extra_stores
    count = await db.scalar(
        select(func.count()).select_from(Store).where(Store.tenant_id == tenant_id)
    )
    if (count or 0) >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Store limit reached for the '{plan.name}' plan ({limit} stores). "
                "Upgrade your plan to add more stores."
            ),
        )


async def check_printer_profile_limit(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    _, plan = await get_active_subscription_with_plan(db, tenant_id)
    if plan.max_printer_profiles == UNLIMITED:
        return

    count = await db.scalar(
        select(func.count())
        .select_from(PrinterProfile)
        .where(PrinterProfile.tenant_id == tenant_id)
    )
    if (count or 0) >= plan.max_printer_profiles:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Printer profile limit reached for the '{plan.name}' plan "
                f"({plan.max_printer_profiles} profiles). Upgrade your plan to add more."
            ),
        )


async def feature_enabled(db: AsyncSession, tenant_id: uuid.UUID, feature_key: str) -> bool:
    _, plan = await get_active_subscription_with_plan(db, tenant_id)
    return bool(plan.features_json.get(feature_key, False))


async def get_saved_bill_days(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """-1 means unlimited (Pro Max), per plans.saved_bill_days."""
    _, plan = await get_active_subscription_with_plan(db, tenant_id)
    return plan.saved_bill_days
