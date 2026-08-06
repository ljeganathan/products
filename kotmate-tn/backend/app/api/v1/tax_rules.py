import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.tax_rules import TaxRuleCreateRequest, TaxRuleResponse, TaxRuleUpdateRequest
from app.services.tax_rule_service import (
    create_tax_rule,
    get_tax_rule_or_404,
    list_tax_rules,
    update_tax_rule,
)

# Managing tax rules is tenant_admin-only (Settings); reads are broad since billing
# (Phase 09) needs to resolve the tenant's default/per-item rates as pos_user too.
router = APIRouter(prefix="/tax-rules", tags=["tax-rules"], dependencies=[Depends(require_tenant_scope)])


@router.get("", response_model=list[TaxRuleResponse])
async def list_tenant_tax_rules(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TaxRuleResponse]:
    rules = await list_tax_rules(db, current_user.tenant_id)
    return [TaxRuleResponse.model_validate(r) for r in rules]


@router.post(
    "",
    response_model=TaxRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def create_tenant_tax_rule(
    payload: TaxRuleCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaxRuleResponse:
    rule = await create_tax_rule(db, current_user.tenant_id, payload)
    await db.commit()
    return TaxRuleResponse.model_validate(rule)


@router.patch(
    "/{tax_rule_id}", response_model=TaxRuleResponse, dependencies=[Depends(require_role("tenant_admin"))]
)
async def update_tenant_tax_rule(
    tax_rule_id: uuid.UUID,
    payload: TaxRuleUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaxRuleResponse:
    rule = await get_tax_rule_or_404(db, current_user.tenant_id, tax_rule_id)
    rule = await update_tax_rule(db, current_user.tenant_id, rule, payload)
    await db.commit()
    return TaxRuleResponse.model_validate(rule)
