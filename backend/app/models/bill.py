import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import BillStatus, PaymentMode


class Bill(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "bills"
    __table_args__ = (
        Index("ix_bills_tenant_store_number", "tenant_id", "store_id", "bill_number", unique=True),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Sequential per store; uniqueness enforced via composite index (see Indexes doc).
    bill_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cashier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    subtotal_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cgst_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sgst_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    round_off_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payment_mode: Mapped[PaymentMode] = mapped_column(
        SAEnum(PaymentMode, name="payment_mode", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[BillStatus] = mapped_column(
        SAEnum(BillStatus, name="bill_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=BillStatus.COMPLETED,
    )
    printed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BillItem(Base, UUIDPKMixin, TimestampMixin):
    """Line item snapshot — no tenant_id; scoped via bill_id per docs/DATABASE_SCHEMA.md."""

    __tablename__ = "bill_items"

    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id"), nullable=False, index=True
    )
    item_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    # Numeric, not Integer: FMCG units include kg/g/l/ml which are commonly fractional.
    qty: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tax_profile_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    line_total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
