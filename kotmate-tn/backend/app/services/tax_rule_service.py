import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TaxRule
from app.schemas.tax_rules import TaxRuleCreateRequest, TaxRuleUpdateRequest


async def list_tax_rules(session: AsyncSession, tenant_id: uuid.UUID) -> list[TaxRule]:
    rows = await session.execute(
        select(TaxRule).where(TaxRule.tenant_id == tenant_id).order_by(TaxRule.name)
    )
    return list(rows.scalars().all())


async def get_tax_rule_or_404(session: AsyncSession, tenant_id: uuid.UUID, tax_rule_id: uuid.UUID) -> TaxRule:
    rule = (
        await session.execute(
            select(TaxRule).where(TaxRule.id == tax_rule_id, TaxRule.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tax rule not found")
    return rule


async def get_default_tax_rule(session: AsyncSession, tenant_id: uuid.UUID) -> TaxRule | None:
    return (
        await session.execute(
            select(TaxRule).where(
                TaxRule.tenant_id == tenant_id, TaxRule.is_default.is_(True), TaxRule.is_active.is_(True)
            )
        )
    ).scalars().first()


async def _clear_existing_default(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Only one `is_default` tax rule per tenant — the single flat rate a Lite tenant
    (and the fallback for any item without its own `tax_class_id` on Pro/Pro Max) uses.
    """
    existing = await get_default_tax_rule(session, tenant_id)
    if existing is not None:
        existing.is_default = False


async def create_tax_rule(session: AsyncSession, tenant_id: uuid.UUID, req: TaxRuleCreateRequest) -> TaxRule:
    if req.is_default:
        await _clear_existing_default(session, tenant_id)
    rule = TaxRule(
        tenant_id=tenant_id,
        name=req.name,
        cgst_rate=req.cgst_rate,
        sgst_rate=req.sgst_rate,
        is_default=req.is_default,
        is_active=True,
    )
    session.add(rule)
    await session.flush()
    return rule


async def update_tax_rule(
    session: AsyncSession, tenant_id: uuid.UUID, rule: TaxRule, req: TaxRuleUpdateRequest
) -> TaxRule:
    data = req.model_dump(exclude_unset=True)
    if data.get("is_default") is True:
        await _clear_existing_default(session, tenant_id)
    for field, value in data.items():
        setattr(rule, field, value)
    await session.flush()
    return rule
