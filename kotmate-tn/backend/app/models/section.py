import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class SeatingSection(UUIDPKMixin, TimestampMixin, Base):
    """AC / Non-AC / Rooftop / Family / Takeaway / Online Delivery (CLAUDE.md §9/§11).
    `is_seating=false` sections (Takeaway, Online Delivery) skip table assignment in POS.
    """

    __tablename__ = "seating_sections"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ta: Mapped[str | None] = mapped_column(String(100))
    is_seating: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (tenant_composite_index("seating_sections"),)


class ItemSectionPrice(UUIDPKMixin, TimestampMixin, Base):
    """Per-item, per-section price override (CLAUDE.md §6/§11) — absence of a row for a
    given (item_id, section_id) means the POS falls back to `items.price`.
    """

    __tablename__ = "item_section_prices"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    item_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("seating_sections.id"), nullable=False
    )
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        tenant_composite_index("item_section_prices"),
        Index("uq_item_section_prices_item_id_section_id", "item_id", "section_id", unique=True),
    )
