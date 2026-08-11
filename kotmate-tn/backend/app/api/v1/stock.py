import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import Tenant
from app.schemas.stock import StockItemResponse, StockUpdateRequest
from app.services.item_service import get_item_or_404
from app.services.stock_service import has_stock_management_feature, list_stock_items, set_item_stock
from app.services.tenant_onboarding import get_active_plan

# KOT screen's Stock Management tab (extends Phase 05/08's soft-inventory feature) —
# tenant_admin and kitchen ("KOT User") both have this screen per CLAUDE.md §5. This
# tab is a Pro/Pro Max-only surface (unlike the underlying badges/decrement, which
# stay on for Lite too — see stock_service.is_stock_tracking_enabled's docstring), so
# the gate here checks the plan feature AND the tenant's own switch, not the
# Lite-inclusive effective flag.
router = APIRouter(prefix="/stock", tags=["stock"], dependencies=[Depends(require_tenant_scope)])

_NOT_ON_PLAN = HTTPException(
    status.HTTP_403_FORBIDDEN,
    "Stock management isn't available on your current plan. Upgrade to Pro to use it.",
)
_TOGGLE_OFF = HTTPException(
    status.HTTP_403_FORBIDDEN,
    "Stock management is turned off for your account — a tenant_admin can turn it on in Settings.",
)


async def _require_stock_management(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    plan = await get_active_plan(db, tenant_id)
    if not has_stock_management_feature(plan.features if plan else None):
        raise _NOT_ON_PLAN
    if not tenant.stock_management_enabled:
        raise _TOGGLE_OFF
    return tenant


@router.get(
    "/items",
    response_model=list[StockItemResponse],
    dependencies=[Depends(require_role("tenant_admin", "kitchen"))],
)
async def list_tenant_stock_items(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StockItemResponse]:
    await _require_stock_management(db, current_user.tenant_id)
    items = await list_stock_items(db, current_user.tenant_id)
    return [StockItemResponse.model_validate(i) for i in items]


@router.patch(
    "/items/{item_id}",
    response_model=StockItemResponse,
    dependencies=[Depends(require_role("tenant_admin", "kitchen"))],
)
async def update_tenant_stock_item(
    item_id: uuid.UUID,
    payload: StockUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StockItemResponse:
    await _require_stock_management(db, current_user.tenant_id)
    item = await get_item_or_404(db, current_user.tenant_id, item_id)
    item = await set_item_stock(db, current_user.tenant_id, item, payload.available_qty, "manual_set")
    await db.commit()
    return StockItemResponse.model_validate(item)
