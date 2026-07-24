import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class TaxProfile(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "tax_profiles"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cgst_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    sgst_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    igst_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
