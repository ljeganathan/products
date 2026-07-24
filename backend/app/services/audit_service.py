import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def record_audit_log(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write an audit trail entry.

    audit_logs.tenant_id is NOT NULL (per docs/DATABASE_SCHEMA.md), so
    platform-level actions (product_owner, no tenant) are not recorded here
    yet — Phase 7 adds a platform-level audit trail for those.
    """
    if tenant_id is None:
        return

    db.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            metadata_json=metadata,
        )
    )
    await db.flush()
