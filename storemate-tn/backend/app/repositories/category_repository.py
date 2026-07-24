import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category


class CategoryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id_for_tenant(
        self, category_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Category | None:
        return await self.db.scalar(
            select(Category).where(Category.id == category_id, Category.tenant_id == tenant_id)
        )

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, *, page: int, page_size: int, search: str | None
    ) -> tuple[list[Category], int]:
        stmt = select(Category).where(Category.tenant_id == tenant_id)
        count_stmt = (
            select(func.count()).select_from(Category).where(Category.tenant_id == tenant_id)
        )

        if search:
            pattern = f"%{search}%"
            search_filter = Category.name_en.ilike(pattern) | Category.name_ta.ilike(pattern)
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total = await self.db.scalar(count_stmt) or 0
        stmt = (
            stmt.order_by(Category.name_en).offset((page - 1) * page_size).limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def list_all_for_tenant(self, tenant_id: uuid.UUID) -> list[Category]:
        result = await self.db.execute(
            select(Category).where(Category.tenant_id == tenant_id).order_by(Category.name_en)
        )
        return list(result.scalars().all())

    async def get_by_name_en_for_tenant(
        self, name_en: str, tenant_id: uuid.UUID
    ) -> Category | None:
        return await self.db.scalar(
            select(Category).where(
                Category.tenant_id == tenant_id, Category.name_en.ilike(name_en)
            )
        )

    async def create(self, category: Category) -> Category:
        self.db.add(category)
        await self.db.flush()
        return category
