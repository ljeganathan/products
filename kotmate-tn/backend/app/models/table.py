import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import TABLE_STATUSES
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class Table(UUIDPKMixin, TimestampMixin, Base):
    """POS table master. `section_id` is required — only seating_sections with
    `is_seating=true` are selectable here (Takeaway/Online Delivery don't get table rows).
    """

    __tablename__ = "tables"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id"), nullable=False
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("seating_sections.id"), nullable=False
    )
    table_number: Mapped[str] = mapped_column(String(20), nullable=False)
    seating_capacity: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        tenant_composite_index("tables"),
        Index(
            "uq_tables_tenant_id_location_id_table_number",
            "tenant_id",
            "location_id",
            "table_number",
            unique=True,
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in TABLE_STATUSES)})", name="ck_tables_status_valid"
        ),
    )
