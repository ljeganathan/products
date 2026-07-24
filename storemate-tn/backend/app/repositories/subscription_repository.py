import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.enums import SubscriptionStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.tenant import Tenant

RequestedPlan = aliased(Plan)


class SubscriptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _joined_query(self):  # noqa: ANN202
        return (
            select(Subscription, Tenant, Plan, RequestedPlan)
            .join(Tenant, Tenant.id == Subscription.tenant_id)
            .join(Plan, Plan.id == Subscription.plan_id)
            .outerjoin(RequestedPlan, RequestedPlan.id == Subscription.requested_plan_id)
        )

    async def get_by_id_joined(
        self, subscription_id: uuid.UUID
    ) -> tuple[Subscription, Tenant, Plan, Plan | None] | None:
        result = await self.db.execute(
            self._joined_query().where(Subscription.id == subscription_id)
        )
        row = result.first()
        if row is None:
            return None
        subscription, tenant, plan, requested_plan = row
        return subscription, tenant, plan, requested_plan

    async def get_active_for_tenant(self, tenant_id: uuid.UUID) -> Subscription | None:
        return await self.db.scalar(
            select(Subscription)
            .where(
                Subscription.tenant_id == tenant_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(Subscription.created_at.desc())
        )

    async def get_active_joined_for_tenant(
        self, tenant_id: uuid.UUID
    ) -> tuple[Subscription, Tenant, Plan, Plan | None] | None:
        result = await self.db.execute(
            self._joined_query()
            .where(
                Subscription.tenant_id == tenant_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(Subscription.created_at.desc())
        )
        row = result.first()
        if row is None:
            return None
        subscription, tenant, plan, requested_plan = row
        return subscription, tenant, plan, requested_plan

    async def list_all(
        self,
        *,
        page: int,
        page_size: int,
        tenant_id: uuid.UUID | None = None,
        status: SubscriptionStatus | None = None,
    ) -> tuple[list[tuple[Subscription, Tenant, Plan, Plan | None]], int]:
        query = self._joined_query()
        if tenant_id is not None:
            query = query.where(Subscription.tenant_id == tenant_id)
        if status is not None:
            query = query.where(Subscription.status == status)

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        result = await self.db.execute(
            query.order_by(Subscription.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = [(s, t, p, rp) for s, t, p, rp in result.all()]
        return rows, total or 0

    async def cancel_active_for_tenant(self, tenant_id: uuid.UUID) -> None:
        existing = await self.get_active_for_tenant(tenant_id)
        if existing is not None:
            existing.status = SubscriptionStatus.CANCELLED

    async def create(self, subscription: Subscription) -> Subscription:
        self.db.add(subscription)
        await self.db.flush()
        return subscription
