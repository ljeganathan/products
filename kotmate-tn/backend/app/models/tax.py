import uuid

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class TaxRule(UUIDPKMixin, TimestampMixin, Base):
    """CGST and SGST are always stored as two distinct rate columns, never a single merged
    'GST' rate — both must render as separate lines on screen and print (CLAUDE.md §9).
    Lite tenants use one (their default) row; Pro/Pro Max can define several and assign
    per item via `items.tax_class_id`.
    """

    __tablename__ = "tax_rules"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cgst_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    sgst_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (tenant_composite_index("tax_rules"),)
