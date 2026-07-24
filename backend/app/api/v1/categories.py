import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.category import Category
from app.models.enums import UserRole
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.schemas.common import PaginatedResponse
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="/categories", tags=["categories"])

require_admin = require_role(UserRole.ADMIN)
require_staff = require_role(UserRole.ADMIN, UserRole.POS_USER)


@router.get("", response_model=PaginatedResponse[CategoryOut])
async def list_categories(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CategoryOut]:
    assert current_user.tenant_id is not None
    repo = CategoryRepository(db)
    categories, total = await repo.list_for_tenant(
        current_user.tenant_id, page=page, page_size=page_size, search=search
    )
    return PaginatedResponse(
        items=[CategoryOut.model_validate(c) for c in categories],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CategoryOut:
    assert current_user.tenant_id is not None
    repo = CategoryRepository(db)

    if payload.parent_category_id is not None:
        parent = await repo.get_by_id_for_tenant(payload.parent_category_id, current_user.tenant_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="parent_category_id does not exist"
            )

    category = Category(
        tenant_id=current_user.tenant_id,
        name_en=payload.name_en,
        name_ta=payload.name_ta,
        parent_category_id=payload.parent_category_id,
        hsn_code=payload.hsn_code,
    )
    await repo.create(category)
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="category.create",
        entity="category",
        entity_id=category.id,
    )
    await db.commit()
    return CategoryOut.model_validate(category)


@router.get("/{category_id}", response_model=CategoryOut)
async def get_category(
    category_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> CategoryOut:
    assert current_user.tenant_id is not None
    repo = CategoryRepository(db)
    category = await repo.get_by_id_for_tenant(category_id, current_user.tenant_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return CategoryOut.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CategoryOut:
    assert current_user.tenant_id is not None
    repo = CategoryRepository(db)
    category = await repo.get_by_id_for_tenant(category_id, current_user.tenant_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "parent_category_id" in update_data and update_data["parent_category_id"] is not None:
        if update_data["parent_category_id"] == category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A category cannot be its own parent",
            )
        parent = await repo.get_by_id_for_tenant(
            update_data["parent_category_id"], current_user.tenant_id
        )
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="parent_category_id does not exist"
            )

    for field, value in update_data.items():
        setattr(category, field, value)

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="category.update",
        entity="category",
        entity_id=category.id,
    )
    await db.commit()
    return CategoryOut.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    assert current_user.tenant_id is not None
    repo = CategoryRepository(db)
    category = await repo.get_by_id_for_tenant(category_id, current_user.tenant_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    await db.delete(category)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category is still referenced by items or sub-categories",
        ) from exc

    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="category.delete",
        entity="category",
        entity_id=category.id,
    )
    await db.commit()
    return None
