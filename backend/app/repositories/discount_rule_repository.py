import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discount_rule import DiscountRule
from app.models.enums import DiscountScope


class DiscountRuleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id_for_tenant(
        self, rule_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> DiscountRule | None:
        return await self.db.scalar(
            select(DiscountRule).where(
                DiscountRule.id == rule_id, DiscountRule.tenant_id == tenant_id
            )
        )

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        scope: DiscountScope | None,
        is_active: bool | None,
    ) -> tuple[list[DiscountRule], int]:
        stmt = select(DiscountRule).where(DiscountRule.tenant_id == tenant_id)
        count_stmt = (
            select(func.count())
            .select_from(DiscountRule)
            .where(DiscountRule.tenant_id == tenant_id)
        )

        if scope is not None:
            stmt = stmt.where(DiscountRule.scope == scope)
            count_stmt = count_stmt.where(DiscountRule.scope == scope)
        if is_active is not None:
            stmt = stmt.where(DiscountRule.is_active == is_active)
            count_stmt = count_stmt.where(DiscountRule.is_active == is_active)

        total = await self.db.scalar(count_stmt) or 0
        stmt = (
            stmt.order_by(DiscountRule.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create(self, rule: DiscountRule) -> DiscountRule:
        self.db.add(rule)
        await self.db.flush()
        return rule
