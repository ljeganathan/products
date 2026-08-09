import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import DiscountRule, Item
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


async def _to_response(db: AsyncSession, rule: DiscountRule) -> DiscountRuleResponse:
    """Attaches the target item's name (item_level rules only) — a display convenience
    so the Settings page doesn't need a second fetch to label the rule's item.
    """
    item_name_en = None
    if rule.item_id is not None:
        item_name_en = (
            await db.execute(select(Item.name_en).where(Item.id == rule.item_id))
        ).scalar_one_or_none()
    # `item_name_en` isn't a mapped column — set as a plain instance attribute so
    # from_attributes picks it up, without persisting anything to the row.
    rule.item_name_en = item_name_en
    return DiscountRuleResponse.model_validate(rule)


@router.get("", response_model=list[DiscountRuleResponse])
async def list_tenant_discount_rules(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DiscountRuleResponse]:
    rules = await list_discount_rules(db, current_user.tenant_id)
    return [await _to_response(db, r) for r in rules]


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
    # Build the response before committing — require_tenant_scope's RLS var is SET
    # LOCAL (transaction-scoped, see deps.py), so it's gone once this transaction ends
    # and the item_name_en lookup below would silently return nothing (Phase 08's
    # kot.py hit the identical bug in set_ticket_status).
    response = await _to_response(db, rule)
    await db.commit()
    return response


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
    response = await _to_response(db, rule)
    await db.commit()
    return response
