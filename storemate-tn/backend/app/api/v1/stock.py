import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.plan_limits import feature_enabled
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.models.item import Item
from app.models.stock import Stock
from app.repositories.item_repository import ItemRepository
from app.repositories.stock_repository import StockMovementRepository, StockRepository
from app.schemas.common import PaginatedResponse
from app.schemas.stock import StockAdjustRequest, StockMovementOut, StockOut
from app.services.audit_service import record_audit_log
from app.services.stock_service import adjust_stock
from app.utils.store_scope import resolve_store_id

router = APIRouter(prefix="/stock", tags=["stock"])

require_admin = require_role(UserRole.ADMIN)
require_staff = require_role(UserRole.ADMIN, UserRole.POS_USER)


def _to_stock_out(stock: Stock, item: Item) -> StockOut:
    return StockOut(
        id=stock.id,
        tenant_id=stock.tenant_id,
        store_id=stock.store_id,
        item_id=stock.item_id,
        item_name_en=item.name_en,
        item_name_ta=item.name_ta,
        barcode=item.barcode,
        batch_no=stock.batch_no,
        expiry_date=stock.expiry_date,
        quantity_on_hand=float(stock.quantity_on_hand),
        reorder_level=float(item.reorder_level),
        low_stock=float(stock.quantity_on_hand) <= float(item.reorder_level),
        last_restocked_at=stock.last_restocked_at,
    )


@router.get("", response_model=PaginatedResponse[StockOut])
async def list_stock(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    store_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[StockOut]:
    assert current_user.tenant_id is not None
    repo = StockRepository(db)
    effective_store_id = store_id or current_user.store_id
    rows, total = await repo.list_for_tenant(
        current_user.tenant_id,
        page=page,
        page_size=page_size,
        store_id=effective_store_id,
        low_stock_only=False,
    )
    return PaginatedResponse(
        items=[_to_stock_out(s, i) for s, i in rows], total=total, page=page, page_size=page_size
    )


@router.get("/low-stock", response_model=PaginatedResponse[StockOut])
async def list_low_stock(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    store_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[StockOut]:
    assert current_user.tenant_id is not None
    if not await feature_enabled(db, current_user.tenant_id, "low_stock_alerts"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Low-stock alerts are a Pro/Pro Max feature. Upgrade your plan to use this.",
        )

    repo = StockRepository(db)
    effective_store_id = store_id or current_user.store_id
    rows, total = await repo.list_for_tenant(
        current_user.tenant_id,
        page=page,
        page_size=page_size,
        store_id=effective_store_id,
        low_stock_only=True,
    )
    return PaginatedResponse(
        items=[_to_stock_out(s, i) for s, i in rows], total=total, page=page, page_size=page_size
    )


@router.post("/adjust", response_model=StockOut, status_code=status.HTTP_201_CREATED)
async def adjust_stock_endpoint(
    payload: StockAdjustRequest,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> StockOut:
    assert current_user.tenant_id is not None
    store_id = resolve_store_id(current_user, payload.store_id)

    item_repo = ItemRepository(db)
    item = await item_repo.get_by_id_for_tenant(payload.item_id, current_user.tenant_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    stock = await adjust_stock(
        db,
        tenant_id=current_user.tenant_id,
        store_id=store_id,
        item_id=payload.item_id,
        change_qty=payload.change_qty,
        reason=payload.reason,
        reference_id=payload.reference_id,
        created_by=current_user.user_id,
    )
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="stock.adjust",
        entity="stock",
        entity_id=stock.id,
        metadata={"change_qty": payload.change_qty, "reason": payload.reason.value},
    )
    await db.commit()
    return _to_stock_out(stock, item)


@router.get("/movements", response_model=PaginatedResponse[StockMovementOut])
async def list_stock_movements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    item_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[StockMovementOut]:
    assert current_user.tenant_id is not None
    repo = StockMovementRepository(db)
    movements, total = await repo.list_for_tenant(
        current_user.tenant_id, page=page, page_size=page_size, item_id=item_id
    )
    return PaginatedResponse(
        items=[StockMovementOut.model_validate(m) for m in movements],
        total=total,
        page=page,
        page_size=page_size,
    )
