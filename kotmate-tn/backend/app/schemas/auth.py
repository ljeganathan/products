from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    # The full login id — for tenant-scoped roles this is the {tenant_code}-{local
    # handle} form composed at user-creation time (Phase 04); product_owner uses a
    # bare, unprefixed id. Deliberately untyped/unvalidated as an email (CLAUDE.md §5).
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
