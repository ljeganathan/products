import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPKMixin:
    """UUID primary key, defense-in-depth against cross-tenant ID enumeration on top of RLS."""

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def tenant_id_column(nullable: bool = False) -> Mapped[uuid.UUID]:
    """Every tenant-scoped table's `tenant_id` FK — called per-model, not via a mixin
    declared_attr, so each concrete model can still define its own __table_args__.
    """
    return mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=nullable
    )


def tenant_composite_index(table_name: str) -> Index:
    """The `(tenant_id, id)` composite index required on every tenant-scoped table."""
    return Index(f"ix_{table_name}_tenant_id_id", "tenant_id", "id")
