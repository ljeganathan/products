import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DiscountRule
from app.schemas.discounts import DiscountRuleCreateRequest, DiscountRuleUpdateRequest


async def list_discount_rules(session: AsyncSession, tenant_id: uuid.UUID) -> list[DiscountRule]:
    rows = await session.execute(
        select(DiscountRule).where(DiscountRule.tenant_id == tenant_id).order_by(DiscountRule.name)
    )
    return list(rows.scalars().all())


async def get_discount_rule_or_404(
    session: AsyncSession, tenant_id: uuid.UUID, rule_id: uuid.UUID
) -> DiscountRule:
    rule = (
        await session.execute(
            select(DiscountRule).where(DiscountRule.id == rule_id, DiscountRule.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount rule not found")
    return rule


async def get_active_coupon(
    session: AsyncSession, tenant_id: uuid.UUID, coupon_code: str
) -> DiscountRule | None:
    return (
        await session.execute(
            select(DiscountRule).where(
                DiscountRule.tenant_id == tenant_id,
                DiscountRule.type == "coupon",
                DiscountRule.coupon_code == coupon_code,
                DiscountRule.is_active.is_(True),
            )
        )
    ).scalars().first()


async def _validate_coupon_code_unique(
    session: AsyncSession, tenant_id: uuid.UUID, coupon_code: str, exclude_id: uuid.UUID | None = None
) -> None:
    query = select(DiscountRule.id).where(
        DiscountRule.tenant_id == tenant_id, DiscountRule.coupon_code == coupon_code
    )
    if exclude_id is not None:
        query = query.where(DiscountRule.id != exclude_id)
    if (await session.execute(query)).scalar_one_or_none() is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "A discount rule with this coupon code already exists"
        )


async def create_discount_rule(
    session: AsyncSession, tenant_id: uuid.UUID, req: DiscountRuleCreateRequest
) -> DiscountRule:
    if req.coupon_code:
        await _validate_coupon_code_unique(session, tenant_id, req.coupon_code)
    rule = DiscountRule(
        tenant_id=tenant_id,
        name=req.name,
        type=req.type,
        value=req.value,
        coupon_code=req.coupon_code,
        is_active=True,
    )
    session.add(rule)
    await session.flush()
    return rule


async def update_discount_rule(
    session: AsyncSession, tenant_id: uuid.UUID, rule: DiscountRule, req: DiscountRuleUpdateRequest
) -> DiscountRule:
    data = req.model_dump(exclude_unset=True)
    if data.get("coupon_code") and rule.type == "coupon":
        await _validate_coupon_code_unique(session, tenant_id, data["coupon_code"], exclude_id=rule.id)
    for field, value in data.items():
        setattr(rule, field, value)
    await session.flush()
    return rule
