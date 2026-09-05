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
    # Tenant-wide toggle for the POS category rail's Tamil labels only (CLAUDE.md §9 still
    # requires item buttons themselves to always show English+Tamil together — this is a
    # narrower, admin-controlled exception scoped to the category rail/strip, not a
    # reversal of that rule). Independent of hotel_master.show_tamil_names, which controls
    # the printed KOT/bill only. Defaults true so existing tenants see no behavior change.
    show_tamil_categories: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Pre-selected payment method on the POS billing screen (tenant-wide, all tiers) —
    # cashiers can still change it per bill.
    default_payment_method: Mapped[str] = mapped_column(String(10), nullable=False, default="cash")
    # Tenant-wide kill switch for printing Reports (Pro Max only — gated separately via
    # plans.features.report_printing). Defaults off, unlike stock_management_enabled's
    # "always on for tiers without the feature" — Lite/Pro never see this at all.
    report_printing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Whether Item Wise Sales / Category Wise Sales report prints show the Tamil name
    # (rasterized as an image on a thermal printer — dot-matrix always falls back to
    # English, same limitation dot-matrix bill/KOT already have) instead of English.
    # Inert unless report_printing_enabled is also on. Defaults off.
    report_tamil_names_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Which POS screen layout this tenant uses — "default" (today's hotkey-driven
    # counter screen) or "guided" (Petpooja-style step-by-step alternative). Every
    # tier, no plan gating — this is a workflow choice, not a premium feature.
    pos_layout: Mapped[str] = mapped_column(String(20), nullable=False, default="default")
    # "Require waiter selection" toggle — admin-settings-only, never exposed on the POS
    # screen itself. Common to both POS layouts: gates whether a waiter must be chosen
    # before a dine-in order can be billed on Default and Guided POS alike (previously
    # Guided-POS-only, with Default hardcoded always-mandatory — that hardcoding is
    # gone, this is now the single source of truth for both). Never applies to
    # non-seating orders (Takeaway/Online Delivery) — those never require a waiter on
    # any layout, regardless of this toggle. Defaults true to match the pre-existing
    # always-mandatory behavior, so no tenant's POS experience changes on deploy.
    waiter_mandatory_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Separate, narrower "Require waiter selection" toggle scoped to non-seating orders
    # only (Takeaway/Online Delivery) — admin-settings-only, never exposed on the POS
    # screen, common to both POS layouts like waiter_mandatory_enabled above. Independent
    # of that toggle: a tenant can require a waiter for dine-in but not takeaway, or vice
    # versa. Defaults False to match today's actual behavior (non-seating never requires
    # a waiter on either layout, regardless of waiter_mandatory_enabled), so no tenant's
    # POS experience changes on deploy.
    waiter_mandatory_non_seating_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint(_STATE_CHECK_SQL, name="ck_tenants_state_valid"),
        CheckConstraint(_PINCODE_CHECK_SQL, name="ck_tenants_pincode_format"),
        CheckConstraint(_TENANT_CODE_CHECK_SQL, name="ck_tenants_tenant_code_format"),
        CheckConstraint(
            "default_payment_method IN ('upi', 'cash', 'card')",
            name="ck_tenants_default_payment_method_valid",
        ),
        CheckConstraint("pos_layout IN ('default', 'guided')", name="ck_tenants_pos_layout_valid"),
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
