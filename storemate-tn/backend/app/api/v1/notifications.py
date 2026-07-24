import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.repositories.notification_repository import NotificationRepository
from app.schemas.common import PaginatedResponse
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Notifications (low-stock alerts etc.) are store-management concerns, same
# audience as the Store Dashboard in CLAUDE.md §5 — admin only.
require_admin = require_role(UserRole.ADMIN)


@router.get("", response_model=PaginatedResponse[NotificationOut])
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    store_id: uuid.UUID | None = Query(None),
    is_read: bool | None = Query(None),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NotificationOut]:
    assert current_user.tenant_id is not None
    effective_store_id = store_id or current_user.store_id
    repo = NotificationRepository(db)
    notifications, total = await repo.list_for_user(
        current_user.tenant_id,
        store_id=effective_store_id,
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
        is_read=is_read,
    )
    return PaginatedResponse(
        items=[NotificationOut.model_validate(n) for n in notifications],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    assert current_user.tenant_id is not None
    repo = NotificationRepository(db)
    notification = await repo.get_by_id_for_tenant(notification_id, current_user.tenant_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.is_read = True
    await db.flush()
    await db.commit()
    return NotificationOut.model_validate(notification)
