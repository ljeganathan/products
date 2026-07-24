import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.repositories.item_repository import ItemRepository
from app.schemas.item import ItemOut

router = APIRouter(prefix="/pos", tags=["pos"])

require_staff = require_role(UserRole.ADMIN, UserRole.POS_USER)


@router.get("/items/search", response_model=list[ItemOut])
async def search_pos_items(
    q: str = Query(..., min_length=1),
    store_id: uuid.UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[ItemOut]:
    """Backs the POS fast-search fallback once the client-side TanStack Query
    item cache (Phase 4) doesn't have a local match — e.g. large catalogs or
    a cold cache right after login."""
    assert current_user.tenant_id is not None
    effective_store_id = store_id or current_user.store_id
    repo = ItemRepository(db)
    items = await repo.search_active_for_pos(current_user.tenant_id, effective_store_id, q, limit)
    return [ItemOut.model_validate(i) for i in items]
