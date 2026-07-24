import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id_for_tenant(
        self, notification_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Notification | None:
        return await self.db.scalar(
            select(Notification).where(
                Notification.id == notification_id, Notification.tenant_id == tenant_id
            )
        )

    async def exists_recent(
        self,
        *,
        tenant_id: uuid.UUID,
        store_id: uuid.UUID,
        reference_id: uuid.UUID,
        notification_type: NotificationType,
        since: datetime,
    ) -> bool:
        """Cooldown/dedup check: has this exact item already triggered this
        notification type since `since`? Used so the same low-stock item
        doesn't re-notify on every sale or every scheduler scan."""
        result = await self.db.scalar(
            select(Notification.id)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.store_id == store_id,
                Notification.reference_id == reference_id,
                Notification.type == notification_type,
                Notification.created_at >= since,
            )
            .limit(1)
        )
        return result is not None

    async def list_for_user(
        self,
        tenant_id: uuid.UUID,
        *,
        store_id: uuid.UUID | None,
        user_id: uuid.UUID,
        page: int,
        page_size: int,
        is_read: bool | None,
    ) -> tuple[list[Notification], int]:
        visible_to_user = or_(
            Notification.created_for_user_id.is_(None),
            Notification.created_for_user_id == user_id,
        )
        stmt = select(Notification).where(Notification.tenant_id == tenant_id, visible_to_user)
        count_stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.tenant_id == tenant_id, visible_to_user)
        )

        if store_id is not None:
            stmt = stmt.where(Notification.store_id == store_id)
            count_stmt = count_stmt.where(Notification.store_id == store_id)
        if is_read is not None:
            stmt = stmt.where(Notification.is_read == is_read)
            count_stmt = count_stmt.where(Notification.is_read == is_read)

        total = await self.db.scalar(count_stmt) or 0
        stmt = (
            stmt.order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
