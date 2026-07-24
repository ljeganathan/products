import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import ItemUnit


class Item(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "items"
    __table_args__ = (
        Index("ix_items_tenant_barcode", "tenant_id", "barcode", unique=True),
        Index("ix_items_tenant_store_name_en", "tenant_id", "store_id", "name_en"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False, index=True
    )
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ta: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Uniqueness enforced per-tenant via a composite index (see migration / Indexes doc).
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unit: Mapped[ItemUnit] = mapped_column(
        SAEnum(ItemUnit, name="item_unit", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    mrp_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    selling_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tax_profiles.id"), nullable=False, index=True
    )
    # Numeric, not Integer: FMCG units include kg/g/l/ml which are commonly fractional.
    reorder_level: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    reorder_qty: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pack_size: Mapped[str | None] = mapped_column(String(30), nullable=True)
    hsn_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    batch_tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
