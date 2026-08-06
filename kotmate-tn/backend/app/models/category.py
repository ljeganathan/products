import uuid

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class Category(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ta: Mapped[str | None] = mapped_column(String(100))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (tenant_composite_index("categories"),)
