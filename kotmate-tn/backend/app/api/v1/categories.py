import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.categories import (
    CategoryCreateRequest,
    CategoryReorderRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)
from app.services.category_service import (
    create_category,
    get_category_or_404,
    list_categories,
    reorder_categories,
    update_category,
)

# Read access is broad (any tenant-scoped role — Phase 07/08 read categories for the
# POS/KOT screens); writes are tenant_admin-only, enforced per-route below.
router = APIRouter(prefix="/categories", tags=["categories"], dependencies=[Depends(require_tenant_scope)])


@router.get("", response_model=list[CategoryResponse])
async def list_tenant_categories(
    current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[CategoryResponse]:
    categories = await list_categories(db, current_user.tenant_id)
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post(
    "", response_model=CategoryResponse, status_code=201, dependencies=[Depends(require_role("tenant_admin"))]
)
async def create_tenant_category(
    payload: CategoryCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    category = await create_category(db, current_user.tenant_id, payload)
    await db.commit()
    return CategoryResponse.model_validate(category)


@router.patch(
    "/{category_id}", response_model=CategoryResponse, dependencies=[Depends(require_role("tenant_admin"))]
)
async def update_tenant_category(
    category_id: uuid.UUID,
    payload: CategoryUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    category = await get_category_or_404(db, current_user.tenant_id, category_id)
    category = await update_category(db, category, payload)
    await db.commit()
    return CategoryResponse.model_validate(category)


@router.put(
    "/reorder", response_model=list[CategoryResponse], dependencies=[Depends(require_role("tenant_admin"))]
)
async def reorder_tenant_categories(
    payload: CategoryReorderRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryResponse]:
    categories = await reorder_categories(db, current_user.tenant_id, payload)
    await db.commit()
    return [CategoryResponse.model_validate(c) for c in categories]
