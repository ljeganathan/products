import uuid
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DiscountRule, Item
from app.schemas.discounts import DiscountRuleCreateRequest, DiscountRuleUpdateRequest


def _today() -> date:
    return datetime.now(UTC).date()


def _is_eligible(rule: DiscountRule, today: date) -> bool:
    """Active + not expired — the single gate every auto-apply lookup below shares."""
    return rule.is_active and (rule.expires_at is None or rule.expires_at >= today)


def rule_amount(rule: DiscountRule, base: float) -> float:
    """The rupee discount a rule contributes against a given base value (a line total
    for item_level, the running bill remainder for flat_percent/coupon).
    """
    if rule.discount_mode == "rupee":
        return float(rule.value or 0)
    return base * float(rule.value or 0) / 100


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
    rule = (
        await session.execute(
            select(DiscountRule).where(
                DiscountRule.tenant_id == tenant_id,
                DiscountRule.type == "coupon",
                DiscountRule.coupon_code == coupon_code,
            )
        )
    ).scalars().first()
    if rule is None or not _is_eligible(rule, _today()):
        return None
    return rule


async def get_best_active_flat_rule(
    session: AsyncSession, tenant_id: uuid.UUID, subtotal: float
) -> DiscountRule | None:
    """If more than one flat rule is active at once, the one that discounts the most
    wins — avoids under-discounting a customer due to arbitrary row order when an admin
    forgets to deactivate an older rule.
    """
    rows = (
        await session.execute(
            select(DiscountRule).where(
                DiscountRule.tenant_id == tenant_id,
                DiscountRule.type == "flat_percent",
                DiscountRule.is_active.is_(True),
            )
        )
    ).scalars().all()
    eligible = [r for r in rows if _is_eligible(r, _today())]
    if not eligible:
        return None
    return max(eligible, key=lambda r: rule_amount(r, subtotal))


async def get_active_item_level_rules(
    session: AsyncSession, tenant_id: uuid.UUID, item_ids: set[uuid.UUID]
) -> dict[uuid.UUID, DiscountRule]:
    """Eligible item_level rules targeting any of `item_ids`, keyed by item_id. If more
    than one active rule somehow targets the same item, the larger-discount one wins
    (same tie-break as flat rules) — computed against that item's own line total by the
    caller, so this just returns candidates per item.
    """
    if not item_ids:
        return {}
    rows = (
        await session.execute(
            select(DiscountRule).where(
                DiscountRule.tenant_id == tenant_id,
                DiscountRule.type == "item_level",
                DiscountRule.is_active.is_(True),
                DiscountRule.item_id.in_(item_ids),
            )
        )
    ).scalars().all()
    by_item: dict[uuid.UUID, list[DiscountRule]] = {}
    for r in rows:
        if r.item_id is not None and _is_eligible(r, _today()):
            by_item.setdefault(r.item_id, []).append(r)
    return {item_id: max(candidates, key=lambda r: r.value or 0) for item_id, candidates in by_item.items()}


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


async def _validate_item_belongs_to_tenant(
    session: AsyncSession, tenant_id: uuid.UUID, item_id: uuid.UUID
) -> None:
    item = (
        await session.execute(select(Item.id).where(Item.id == item_id, Item.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "item_id does not belong to this tenant")


async def create_discount_rule(
    session: AsyncSession, tenant_id: uuid.UUID, req: DiscountRuleCreateRequest
) -> DiscountRule:
    if req.coupon_code:
        await _validate_coupon_code_unique(session, tenant_id, req.coupon_code)
    if req.item_id:
        await _validate_item_belongs_to_tenant(session, tenant_id, req.item_id)
    rule = DiscountRule(
        tenant_id=tenant_id,
        name=req.name,
        type=req.type,
        discount_mode=req.discount_mode,
        value=req.value,
        item_id=req.item_id,
        coupon_code=req.coupon_code,
        expires_at=req.expires_at,
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
    if data.get("item_id") and rule.type == "item_level":
        await _validate_item_belongs_to_tenant(session, tenant_id, data["item_id"])

    effective_mode = data.get("discount_mode", rule.discount_mode)
    effective_value = data.get("value", rule.value)
    if effective_mode == "percent" and effective_value is not None and effective_value > 100:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "value cannot exceed 100 when discount_mode=percent")

    for field, value in data.items():
        setattr(rule, field, value)
    await session.flush()
    return rule
