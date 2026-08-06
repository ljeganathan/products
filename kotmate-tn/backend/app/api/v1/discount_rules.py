import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.discounts import DiscountRuleCreateRequest, DiscountRuleResponse, DiscountRuleUpdateRequest
from app.services.discount_rule_service import (
    create_discount_rule,
    get_discount_rule_or_404,
    list_discount_rules,
    update_discount_rule,
)

# Managing discount/coupon rules is tenant_admin-only (Settings); reads are broad since
# billing (Phase 09) needs to resolve a coupon code as pos_user too.
router = APIRouter(
    prefix="/discount-rules", tags=["discount-rules"], dependencies=[Depends(require_tenant_scope)]
)


@router.get("", response_model=list[DiscountRuleResponse])
async def list_tenant_discount_rules(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiscountRuleResponse]:
    rules = await list_discount_rules(db, current_user.tenant_id)
    return [DiscountRuleResponse.model_validate(r) for r in rules]


@router.post(
    "",
    response_model=DiscountRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def create_tenant_discount_rule(
    payload: DiscountRuleCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DiscountRuleResponse:
    rule = await create_discount_rule(db, current_user.tenant_id, payload)
    await db.commit()
    return DiscountRuleResponse.model_validate(rule)


@router.patch(
    "/{discount_rule_id}",
    response_model=DiscountRuleResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def update_tenant_discount_rule(
    discount_rule_id: uuid.UUID,
    payload: DiscountRuleUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DiscountRuleResponse:
    rule = await get_discount_rule_or_404(db, current_user.tenant_id, discount_rule_id)
    rule = await update_discount_rule(db, current_user.tenant_id, rule, payload)
    await db.commit()
    return DiscountRuleResponse.model_validate(rule)
