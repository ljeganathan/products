import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class AuditLog(UUIDPKMixin, TimestampMixin, Base):
    """Manual price overrides & discounts above a configurable threshold (CLAUDE.md §11)."""

    __tablename__ = "audit_log"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    user_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    details: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (tenant_composite_index("audit_log"),)
