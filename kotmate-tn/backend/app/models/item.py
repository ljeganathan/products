import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class Item(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "items"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    category_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    name_ta: Mapped[str | None] = mapped_column(String(150))
    image_url: Mapped[str | None] = mapped_column(String(500))
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    tax_class_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tax_rules.id")
    )
    # Short code printed on a counter menu card for POS numeric quick-entry (CLAUDE.md §9).
    item_code: Mapped[str | None] = mapped_column(String(20))
    is_top_seller: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Meals/Thali-style combo — POS renders these as an oversized tile (CLAUDE.md §9).
    is_combo_tile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Soft inventory awareness, opt-in per item (CLAUDE.md §11) — not a full inventory
    # ledger. available_qty is only meaningful while track_inventory is true; toggling
    # tracking off clears it back to NULL rather than leaving a stale count hidden.
    track_inventory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    available_qty: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        tenant_composite_index("items"),
        Index(
            "uq_items_tenant_id_item_code",
            "tenant_id",
            "item_code",
            unique=True,
            postgresql_where=text("item_code IS NOT NULL"),
        ),
        # Trigram GIN indexes power `GET /api/v1/items/search` (Phase 07, CLAUDE.md §9)
        # — typo-tolerant partial-match search that stays fast on a 500-item catalog,
        # which a plain B-tree/ILIKE scan can't do. Requires the pg_trgm extension
        # (enabled in the same migration that adds these indexes).
        Index(
            "ix_items_name_en_trgm",
            "name_en",
            postgresql_using="gin",
            postgresql_ops={"name_en": "gin_trgm_ops"},
        ),
        Index(
            "ix_items_name_ta_trgm",
            "name_ta",
            postgresql_using="gin",
            postgresql_ops={"name_ta": "gin_trgm_ops"},
        ),
    )
