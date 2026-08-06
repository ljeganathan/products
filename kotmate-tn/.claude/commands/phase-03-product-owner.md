# /phase-03-product-owner

Read `CLAUDE.md` §5, §6, §7 before starting.

## Goal
Product Owner console: tenant onboarding, subscription/plan management, and platform maintenance page.

## Scope
1. **Backend** (`/api/v1/platform/*`, `product_owner` role only)
   - CRUD tenants (create tenant — Company Master: company name + Indian-format address (door_no/street/city/district/state/pincode, CLAUDE.md §8/§9) + a system-generated unique `tenant_code` (short, uppercase, e.g. derived from company-name initials with a numeric suffix on collision; shown to the product owner so they can hand it to the customer) — + first admin user (local handle + password; the actual `users.user_id` stored/returned is `{tenant_code}-{local_handle}`, never email, per CLAUDE.md §5) + one default `tenant_location` in one transaction). Tenant creation also seeds default `seating_sections` (AC, Non-AC, Rooftop, Family, Takeaway, Online Delivery) for that tenant.
   - CRUD subscriptions (assign plan, activate/suspend/cancel, track billing cycle dates, manual payment status flag for now — payment gateway is a future phase). Plan choice sets both `max_users` and `max_locations` (Lite=1/Pro=2/Pro Max=5 locations, per CLAUDE.md §6/§7).
   - CRUD plans/feature flags (so Senthil can tweak Lite/Pro/Pro Max features without a redeploy — plan `features` JSONB editable via UI, `max_users`/`max_locations` as first-class editable fields since they're enforced server-side, not just flags).
   - Platform maintenance endpoints: maintenance-mode toggle (blocks tenant logins with a message, product_owner exempt), broadcast announcement banner, basic system health/metrics endpoint (active tenants, MRR estimate, seat usage, location usage vs cap).
2. **Frontend** (`/platform/*`)
   - Tenant list/detail with subscription status, seat usage vs plan cap.
   - Plan editor (checkbox/JSON feature matrix editor).
   - Maintenance-mode toggle + announcement banner composer.
   - Simple MRR/active-tenant KPI cards (reuses dashboard chart components once Phase 11 lands; stub with basic numbers for now).

## Acceptance Criteria
- Product owner can create a new tenant end-to-end and log in as that tenant's admin.
- Changing a tenant's plan immediately changes which features that tenant's frontend can access (feature flags read from `/auth/me` or a `/me/features` endpoint).
- Maintenance mode blocks a non-product-owner login with a friendly message.
