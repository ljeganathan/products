import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StockMovementReason
from app.models.stock import Stock, StockMovement
from app.repositories.stock_repository import StockMovementRepository, StockRepository


async def adjust_stock(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
    item_id: uuid.UUID,
    change_qty: float,
    reason: StockMovementReason,
    reference_id: uuid.UUID | None,
    created_by: uuid.UUID,
) -> Stock:
    """Writes both `stock` and `stock_movements` within the caller's existing
    session/transaction, so a single `db.commit()` makes both changes atomic."""
    stock_repo = StockRepository(db)
    movement_repo = StockMovementRepository(db)

    stock = await stock_repo.get_by_item_store(tenant_id, store_id, item_id)
    if stock is None:
        if change_qty < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove stock for an item that has no existing stock record",
            )
        stock = Stock(tenant_id=tenant_id, store_id=store_id, item_id=item_id, quantity_on_hand=0)
        await stock_repo.create(stock)

    new_qty = float(stock.quantity_on_hand) + change_qty
    if new_qty < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient stock: {stock.quantity_on_hand} on hand, "
                f"cannot apply change of {change_qty}"
            ),
        )

    stock.quantity_on_hand = new_qty
    if change_qty > 0:
        stock.last_restocked_at = datetime.now(UTC)
    await db.flush()

    await movement_repo.create(
        StockMovement(
            tenant_id=tenant_id,
            store_id=store_id,
            item_id=item_id,
            change_qty=change_qty,
            reason=reason,
            reference_id=reference_id,
            created_by=created_by,
        )
    )
    return stock
