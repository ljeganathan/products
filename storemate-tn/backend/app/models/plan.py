from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import PlanCode


class Plan(Base, UUIDPKMixin, TimestampMixin):
    """Platform-level plan definition (product_owner scope, no tenant_id)."""

    __tablename__ = "plans"

    code: Mapped[PlanCode] = mapped_column(
        SAEnum(PlanCode, name="plan_code", values_callable=lambda x: [e.value for e in x]),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # -1 means unlimited (e.g. Pro Max users/stores), matching saved_bill_days below.
    max_users: Mapped[int] = mapped_column(Integer, nullable=False)
    max_stores: Mapped[int] = mapped_column(Integer, nullable=False)
    max_printer_profiles: Mapped[int] = mapped_column(Integer, nullable=False)
    low_stock_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    saved_bill_days: Mapped[int] = mapped_column(Integer, nullable=False)  # -1 = unlimited
    features_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
