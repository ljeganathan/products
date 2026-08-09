import uuid

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import INDIAN_STATES
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column

_STATE_CHECK_SQL = "state IN ({})".format(", ".join(f"'{s}'" for s in INDIAN_STATES))
_PINCODE_CHECK_SQL = "pincode ~ '^[1-9][0-9]{5}$'"
_TENANT_CODE_CHECK_SQL = "tenant_code ~ '^[A-Z0-9]{2,10}$'"


class Tenant(UUIDPKMixin, TimestampMixin, Base):
    """One row per subscribing Company account — the Company Master (CLAUDE.md §4).

    `tenant_code` is a short, unique, platform-assigned prefix (Phase 03) that composes
    every tenant-scoped user's login id as `{tenant_code}{local_handle}` (CLAUDE.md §5,
    no separator, e.g. "HNRADMIN") so `users.user_id` can be a single globally-unique
    login field with no separate company/tenant selector on the login form, even though
    two tenants may pick the same local handle (e.g. both wanting "admin01").
    """

    __tablename__ = "tenants"

    tenant_code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))
    door_no: Mapped[str | None] = mapped_column(String(50))
    street: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(50))
    pincode: Mapped[str | None] = mapped_column(String(6))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Tenant-wide kill switch for stock-quantity tracking (only meaningful on Pro/Pro
    # Max — gated separately via plans.features.stock_management). Soft-disable only:
    # toggling this off never clears items.track_inventory/available_qty, so re-enabling
    # restores prior config exactly.
    stock_management_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint(_STATE_CHECK_SQL, name="ck_tenants_state_valid"),
        CheckConstraint(_PINCODE_CHECK_SQL, name="ck_tenants_pincode_format"),
        CheckConstraint(_TENANT_CODE_CHECK_SQL, name="ck_tenants_tenant_code_format"),
    )


class TenantLocation(UUIDPKMixin, TimestampMixin, Base):
    """One row per hotel location owned by a company, capped by plans.max_locations (CLAUDE.md §4/§6)."""

    __tablename__ = "tenant_locations"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    door_no: Mapped[str | None] = mapped_column(String(50))
    street: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(50))
    pincode: Mapped[str | None] = mapped_column(String(6))
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        tenant_composite_index("tenant_locations"),
        CheckConstraint(_STATE_CHECK_SQL, name="ck_tenant_locations_state_valid"),
        CheckConstraint(_PINCODE_CHECK_SQL, name="ck_tenant_locations_pincode_format"),
    )
