import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class CompanySettings(Base, UUIDPKMixin, TimestampMixin):
    """One row per store — the invoice-header / store master record."""

    __tablename__ = "company_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable at the DB level so pre-existing rows don't break the migration;
    # enforced as mandatory in the API layer instead (see api/v1/company_settings.py).
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    fssai_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    invoice_footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
