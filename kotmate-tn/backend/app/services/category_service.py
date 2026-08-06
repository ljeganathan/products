import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category
from app.schemas.categories import CategoryCreateRequest, CategoryReorderRequest, CategoryUpdateRequest


async def list_categories(session: AsyncSession, tenant_id: uuid.UUID) -> list[Category]:
    rows = await session.execute(
        select(Category).where(Category.tenant_id == tenant_id).order_by(Category.display_order)
    )
    return list(rows.scalars().all())


async def get_category_or_404(
    session: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID
) -> Category:
    category = (
        await session.execute(
            select(Category).where(Category.id == category_id, Category.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return category


async def create_category(
    session: AsyncSession, tenant_id: uuid.UUID, req: CategoryCreateRequest
) -> Category:
    display_order = req.display_order
    if display_order is None:
        max_order = (
            await session.execute(
                select(func.max(Category.display_order)).where(Category.tenant_id == tenant_id)
            )
        ).scalar_one()
        display_order = (max_order + 1) if max_order is not None else 0

    category = Category(
        tenant_id=tenant_id,
        name_en=req.name_en,
        name_ta=req.name_ta,
        display_order=display_order,
        is_active=True,
    )
    session.add(category)
    await session.flush()
    return category


async def update_category(session: AsyncSession, category: Category, req: CategoryUpdateRequest) -> Category:
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await session.flush()
    return category


async def reorder_categories(
    session: AsyncSession, tenant_id: uuid.UUID, req: CategoryReorderRequest
) -> list[Category]:
    ids = [entry.id for entry in req.categories]
    existing = (
        await session.execute(
            select(Category.id).where(Category.tenant_id == tenant_id, Category.id.in_(ids))
        )
    ).scalars().all()
    if set(existing) != set(ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "One or more categories do not belong to this tenant"
        )

    order_by_id = {entry.id: entry.display_order for entry in req.categories}
    categories = await list_categories(session, tenant_id)
    for category in categories:
        if category.id in order_by_id:
            category.display_order = order_by_id[category.id]
    await session.flush()
    return await list_categories(session, tenant_id)
