from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    # The full login id — for tenant-scoped roles this is the {tenant_code}{local
    # handle} form (no separator) composed at user-creation time (Phase 04);
    # product_owner uses a bare, unprefixed id. Deliberately untyped/unvalidated as an
    # email (CLAUDE.md §5).
    user_id: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: str | None
    login_id: str


class MeResponse(BaseModel):
    """Phase 03 (CLAUDE.md §11) — frontend feature-gating reads `features`/`max_users`/
    `max_locations` from here so a plan change (product_owner console) takes effect the
    next time this is fetched, no redeploy needed. Null tenant/plan fields for
    `product_owner`, who has no tenant.
    """

    login_id: str
    role: str
    tenant_id: str | None
    tenant_code: str | None
    company_name: str | None
    plan_code: str | None
    max_users: int | None
    max_locations: int | None
    features: dict | None
    # Effective stock-quantity-tracking state (tenant toggle AND plan has the feature)
    # — the single flag every frontend surface should check (CLAUDE.md §11 extension).
    stock_tracking_enabled: bool
    # Tenant toggle for Tamil labels on the POS category rail/strip only (not gated by
    # plan) — item buttons still always show both languages per CLAUDE.md §9.
    show_tamil_categories: bool
    # Pre-selected payment method on the POS billing screen (tenant-wide, all tiers).
    default_payment_method: str
    # Tenant-wide kill switch for printing reports (Pro Max only — always false when the
    # plan lacks the feature, mirroring stock_tracking_enabled's shape).
    report_printing_enabled: bool
    # Whether Item Wise/Category Wise report prints show the Tamil name instead of
    # English — raw tenant value, not derived, since it's inert unless
    # report_printing_enabled is already true.
    report_tamil_names_enabled: bool
    # Which POS screen layout this tenant uses ("default"/"guided") — raw tenant value,
    # not plan-gated. "default" for product_owner, who has no tenant.
    pos_layout: str
    # "Require waiter selection" toggle, common to both POS layouts — raw tenant
    # value. Never applies to non-seating orders on either layout. True for
    # product_owner, matching the pre-existing always-mandatory default.
    waiter_mandatory_enabled: bool
