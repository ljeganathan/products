import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import PRINTER_CONNECTION_TYPES, PRINTER_TARGETS, PRINTER_TYPES
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class Printer(UUIDPKMixin, TimestampMixin, Base):
    """KOT printer + Bill printer can differ, scoped per location (CLAUDE.md §10)."""

    __tablename__ = "printers"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target: Mapped[str] = mapped_column(String(10), nullable=False)
    printer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    connection_type: Mapped[str] = mapped_column(String(20), nullable=False)
    connection_details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        tenant_composite_index("printers"),
        CheckConstraint(
            f"target IN ({', '.join(repr(t) for t in PRINTER_TARGETS)})", name="ck_printers_target_valid"
        ),
        CheckConstraint(
            f"printer_type IN ({', '.join(repr(t) for t in PRINTER_TYPES)})",
            name="ck_printers_printer_type_valid",
        ),
        CheckConstraint(
            f"connection_type IN ({', '.join(repr(t) for t in PRINTER_CONNECTION_TYPES)})",
            name="ck_printers_connection_type_valid",
        ),
    )
