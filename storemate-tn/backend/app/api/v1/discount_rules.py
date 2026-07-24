import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.plan_limits import feature_enabled
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.discount_rule import DiscountRule
from app.models.enums import DiscountScope, UserRole
from app.repositories.discount_rule_repository import DiscountRuleRepository
from app.schemas.common import PaginatedResponse
from app.schemas.discount_rule import DiscountRuleCreate, DiscountRuleOut, DiscountRuleUpdate
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="/discount-rules", tags=["discount-rules"])

require_admin = require_role(UserRole.ADMIN)

UPGRADE_MESSAGE = "Discount rules are a Pro/Pro Max feature. Upgrade your plan to use this."


async def _require_feature(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    if not await feature_enabled(db, tenant_id, "discount_rules_advanced"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=UPGRADE_MESSAGE)


@router.get("", response_model=PaginatedResponse[DiscountRuleOut])
async def list_discount_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scope: DiscountScope | None = Query(None),
    is_active: bool | None = Query(None),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[DiscountRuleOut]:
    assert current_user.tenant_id is not None
    await _require_feature(db, current_user.tenant_id)

    repo = DiscountRuleRepository(db)
    rules, total = await repo.list_for_tenant(
        current_user.tenant_id, page=page, page_size=page_size, scope=scope, is_active=is_active
    )
    return PaginatedResponse(
        items=[DiscountRuleOut.model_validate(r) for r in rules],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=DiscountRuleOut, status_code=status.HTTP_201_CREATED)
async def create_discount_rule(
    payload: DiscountRuleCreate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DiscountRuleOut:
    assert current_user.tenant_id is not None
    await _require_feature(db, current_user.tenant_id)

    rule = DiscountRule(
        tenant_id=current_user.tenant_id,
        scope=payload.scope,
        target_id=payload.target_id,
        type=payload.type,
        value=payload.value,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        is_active=payload.is_active,
    )
    repo = DiscountRuleRepository(db)
    await repo.create(rule)
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="discount_rule.create",
        entity="discount_rule",
        entity_id=rule.id,
    )
    await db.commit()
    return DiscountRuleOut.model_validate(rule)


@router.patch("/{rule_id}", response_model=DiscountRuleOut)
async def update_discount_rule(
    rule_id: uuid.UUID,
    payload: DiscountRuleUpdate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DiscountRuleOut:
    assert current_user.tenant_id is not None
    await _require_feature(db, current_user.tenant_id)

    repo = DiscountRuleRepository(db)
    rule = await repo.get_by_id_for_tenant(rule_id, current_user.tenant_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount rule not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="discount_rule.update",
        entity="discount_rule",
        entity_id=rule.id,
    )
    await db.commit()
    return DiscountRuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_discount_rule(
    rule_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    assert current_user.tenant_id is not None
    await _require_feature(db, current_user.tenant_id)

    repo = DiscountRuleRepository(db)
    rule = await repo.get_by_id_for_tenant(rule_id, current_user.tenant_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount rule not found")

    await db.delete(rule)
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="discount_rule.delete",
        entity="discount_rule",
        entity_id=rule.id,
    )
    await db.commit()
    return None
