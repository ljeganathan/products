# /phase-13-platform-console-ux

Read `CLAUDE.md` §5 before starting.

## Goal
Fix Product Owner console UX/data gaps surfaced in manual testing: an unreachable logout button, no home link, a login-id format change, missing tenant edit/contact capture, and admin-triggered password reset for a tenant's own admin account.

## Scope
1. **Backend**
   - `Tenant` model gains `email`, `phone` (both nullable) — new Alembic migration, added to `TenantCreateRequest`/`TenantUpdateRequest`/`TenantDetail`.
   - Login-id composition for tenant-scoped roles changes from `{tenant_code}-{local_handle}` to `{tenant_code}{local_handle}` (no separator, CLAUDE.md §5) in both `user_management.create_user` and `tenant_onboarding.onboard_tenant`. Accounts created before this change keep their hyphenated id — not renamed retroactively. `user_management._to_response` strips whichever prefix form (hyphenated or not) is actually present when reconstructing `local_handle` for display.
   - New `POST /api/v1/platform/tenants/{id}/reset-admin-password` (platform_admin-scoped): resets that tenant's oldest active `tenant_admin` account to a generated one-time password, returned once in the response (never logged).
2. **Frontend**
   - `PlatformShell.tsx`: sidebar gets its own `h-screen`/independent-scroll nav region so the logout button stays reachable regardless of nav-list length; "KOTMate TN" header text becomes a `Link` to `/platform`.
   - `TenantCreatePage.tsx`: add Email/Phone fields to the Company Master fieldset.
   - `TenantDetailPage.tsx`: replace the read-only company/address block with an editable form (Save/Cancel) wired to `PATCH /platform/tenants/{id}`; add a "Reset Admin Password" button showing the one-time password once, dismissible.

## Acceptance Criteria
- Product owner can log out from the platform console regardless of how many tenants/nav items are rendered, without scrolling past content to find the button.
- Clicking "KOTMate TN" from any platform screen returns to `/platform`.
- A newly created tenant's admin login id has no hyphen (e.g. `HTL1ADMIN01`); a pre-existing hyphenated login still authenticates and still displays its correct local handle in User Management.
- Product owner can edit a tenant's company name, email, phone, and address from the tenant detail page, and the change persists.
- Product owner can reset a tenant admin's password and receives a one-time temporary password to hand off out-of-band.
