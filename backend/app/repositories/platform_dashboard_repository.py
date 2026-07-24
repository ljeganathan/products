from datetime import datetime
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InvoiceStatus, SubscriptionStatus, TenantStatus
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionInvoice
from app.models.tenant import Tenant
from app.services.subscription_service import EXTRA_STORE_PRICE_PAISE, EXTRA_USER_PRICE_PAISE


class PlanMixRow(TypedDict):
    plan_code: str
    plan_name: str
    tenant_count: int


class PlatformDashboard(TypedDict):
    active_tenant_count: int
    trialing_count: int
    churned_this_month_count: int
    mrr_paise: int
    plan_mix: list[PlanMixRow]
    overdue_invoices_count: int


class PlatformDashboardRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_dashboard(self, *, month_start: datetime) -> PlatformDashboard:
        active_tenant_count = (
            await self.db.scalar(
                select(func.count()).select_from(Tenant).where(Tenant.status == TenantStatus.ACTIVE)
            )
            or 0
        )
        trialing_count = (
            await self.db.scalar(
                select(func.count()).select_from(Tenant).where(Tenant.status == TenantStatus.TRIAL)
            )
            or 0
        )
        # No dedicated "cancelled_at" column — `updated_at` is the closest
        # proxy for when a tenant's status last changed (see
        # docs/DATABASE_SCHEMA.md; TimestampMixin bumps it on every update).
        churned_this_month_count = (
            await self.db.scalar(
                select(func.count())
                .select_from(Tenant)
                .where(Tenant.status == TenantStatus.CANCELLED, Tenant.updated_at >= month_start)
            )
            or 0
        )

        active_subs = await self.db.execute(
            select(
                Plan.code,
                Plan.name,
                Plan.price_paise,
                Subscription.extra_users,
                Subscription.extra_stores,
            )
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
        )
        mrr_paise = 0
        plan_mix_counts: dict[tuple[str, str], int] = {}
        for code, name, price_paise, extra_users, extra_stores in active_subs.tuples().all():
            mrr_paise += (
                price_paise
                + extra_users * EXTRA_USER_PRICE_PAISE
                + extra_stores * EXTRA_STORE_PRICE_PAISE
            )
            key = (code.value, name)
            plan_mix_counts[key] = plan_mix_counts.get(key, 0) + 1

        plan_mix: list[PlanMixRow] = [
            {"plan_code": code, "plan_name": name, "tenant_count": count}
            for (code, name), count in plan_mix_counts.items()
        ]

        # No dedicated "overdue" invoice status — `failed` is the console's
        # established mapping for it (see api/v1/platform_invoices.py).
        overdue_invoices_count = (
            await self.db.scalar(
                select(func.count())
                .select_from(SubscriptionInvoice)
                .where(SubscriptionInvoice.status == InvoiceStatus.FAILED)
            )
            or 0
        )

        return {
            "active_tenant_count": active_tenant_count,
            "trialing_count": trialing_count,
            "churned_this_month_count": churned_this_month_count,
            "mrr_paise": mrr_paise,
            "plan_mix": plan_mix,
            "overdue_invoices_count": overdue_invoices_count,
        }
