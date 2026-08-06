from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Plan, Role, Subscription, Tenant, TenantLocation, User
from app.schemas.platform import PlatformMetrics

router = APIRouter(prefix="/metrics", tags=["platform-metrics"])


@router.get("", response_model=PlatformMetrics)
async def get_platform_metrics(db: AsyncSession = Depends(get_db)) -> PlatformMetrics:
    active_tenants = (
        await db.execute(select(func.count()).select_from(Tenant).where(Tenant.is_active.is_(True)))
    ).scalar_one()

    # MRR: every active subscription's plan price, yearly plans amortized to a monthly figure.
    active_subs = (
        await db.execute(
            select(
                Subscription.billing_cycle,
                Plan.price_monthly,
                Plan.price_yearly,
                Plan.max_locations,
                Plan.max_users,
            )
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.status == "active")
        )
    ).all()
    mrr_estimate = sum(
        float(row.price_monthly) if row.billing_cycle == "monthly" else float(row.price_yearly) / 12
        for row in active_subs
    )
    total_max_locations = sum(row.max_locations for row in active_subs)
    # NULL max_users means "unlimited" (Pro Max, CLAUDE.md §6) — SQL SUM() silently
    # skips NULLs, which would understate the aggregate cap, so detect it explicitly
    # and report the total as unbounded rather than a misleadingly finite number.
    total_max_users = (
        None
        if any(row.max_users is None for row in active_subs)
        else sum(row.max_users for row in active_subs)
    )

    total_active_users = (
        await db.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.is_active.is_(True),
                User.role_id.in_(select(Role.id).where(Role.code.in_(["tenant_admin", "pos_user"]))),
            )
        )
    ).scalar_one()

    total_active_locations = (
        await db.execute(
            select(func.count()).select_from(TenantLocation).where(TenantLocation.is_active.is_(True))
        )
    ).scalar_one()

    return PlatformMetrics(
        active_tenant_count=active_tenants,
        mrr_estimate=round(mrr_estimate, 2),
        total_active_users=total_active_users,
        total_max_users=total_max_users,
        total_active_locations=total_active_locations,
        total_max_locations=total_max_locations,
    )
