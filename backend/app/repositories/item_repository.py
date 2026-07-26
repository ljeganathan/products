import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item


class ItemRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id_for_tenant(self, item_id: uuid.UUID, tenant_id: uuid.UUID) -> Item | None:
        return await self.db.scalar(
            select(Item).where(Item.id == item_id, Item.tenant_id == tenant_id)
        )

    async def get_by_barcode(self, tenant_id: uuid.UUID, barcode: str) -> Item | None:
        return await self.db.scalar(
            select(Item).where(Item.tenant_id == tenant_id, Item.barcode == barcode)
        )

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        page: int,
        page_size: int,
        search: str | None,
        category_id: uuid.UUID | None,
        store_id: uuid.UUID | None,
    ) -> tuple[list[Item], int]:
        stmt = select(Item).where(Item.tenant_id == tenant_id)
        count_stmt = select(func.count()).select_from(Item).where(Item.tenant_id == tenant_id)

        if store_id is not None:
            stmt = stmt.where(Item.store_id == store_id)
            count_stmt = count_stmt.where(Item.store_id == store_id)
        if category_id is not None:
            stmt = stmt.where(Item.category_id == category_id)
            count_stmt = count_stmt.where(Item.category_id == category_id)
        if search:
            pattern = f"%{search}%"
            search_filter = (
                Item.name_en.ilike(pattern) | Item.name_ta.ilike(pattern) | Item.sku.ilike(pattern)
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total = await self.db.scalar(count_stmt) or 0
        stmt = stmt.order_by(Item.name_en).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def list_all_for_tenant(
        self, tenant_id: uuid.UUID, store_id: uuid.UUID | None
    ) -> list[Item]:
        stmt = select(Item).where(Item.tenant_id == tenant_id)
        if store_id is not None:
            stmt = stmt.where(Item.store_id == store_id)
        stmt = stmt.order_by(Item.name_en)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, item: Item) -> Item:
        self.db.add(item)
        await self.db.flush()
        return item

    async def search_active_for_pos(
        self,
        tenant_id: uuid.UUID,
        store_id: uuid.UUID | None,
        query: str,
        limit: int,
    ) -> list[Item]:
        """Fast POS type-ahead: active items only, matches name/SKU/barcode."""
        pattern = f"%{query}%"
        stmt = select(Item).where(
            Item.tenant_id == tenant_id,
            Item.is_active.is_(True),
            Item.name_en.ilike(pattern)
            | Item.name_ta.ilike(pattern)
            | Item.sku.ilike(pattern)
            | Item.barcode.ilike(pattern),
        )
        if store_id is not None:
            stmt = stmt.where(Item.store_id == store_id)
        stmt = stmt.order_by(Item.name_en).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
