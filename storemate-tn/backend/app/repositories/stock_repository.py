import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.models.stock import Stock, StockMovement


class StockRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_item_store(
        self, tenant_id: uuid.UUID, store_id: uuid.UUID, item_id: uuid.UUID
    ) -> Stock | None:
        return await self.db.scalar(
            select(Stock).where(
                Stock.tenant_id == tenant_id, Stock.store_id == store_id, Stock.item_id == item_id
            )
        )

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        store_id: uuid.UUID | None,
        low_stock_only: bool,
    ) -> tuple[list[tuple[Stock, Item]], int]:
        stmt = (
            select(Stock, Item)
            .join(Item, Item.id == Stock.item_id)
            .where(Stock.tenant_id == tenant_id)
        )
        count_stmt = (
            select(func.count())
            .select_from(Stock)
            .join(Item, Item.id == Stock.item_id)
            .where(Stock.tenant_id == tenant_id)
        )

        if store_id is not None:
            stmt = stmt.where(Stock.store_id == store_id)
            count_stmt = count_stmt.where(Stock.store_id == store_id)
        if low_stock_only:
            stmt = stmt.where(Stock.quantity_on_hand <= Item.reorder_level)
            count_stmt = count_stmt.where(Stock.quantity_on_hand <= Item.reorder_level)

        total = await self.db.scalar(count_stmt) or 0
        stmt = stmt.order_by(Item.name_en).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.tuples().all()), total

    async def create(self, stock: Stock) -> Stock:
        self.db.add(stock)
        await self.db.flush()
        return stock


class StockMovementRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, movement: StockMovement) -> StockMovement:
        self.db.add(movement)
        await self.db.flush()
        return movement

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        item_id: uuid.UUID | None,
    ) -> tuple[list[StockMovement], int]:
        stmt = select(StockMovement).where(StockMovement.tenant_id == tenant_id)
        count_stmt = (
            select(func.count())
            .select_from(StockMovement)
            .where(StockMovement.tenant_id == tenant_id)
        )

        if item_id is not None:
            stmt = stmt.where(StockMovement.item_id == item_id)
            count_stmt = count_stmt.where(StockMovement.item_id == item_id)

        total = await self.db.scalar(count_stmt) or 0
        stmt = (
            stmt.order_by(StockMovement.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
