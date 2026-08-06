# /phase-02-auth-rbac

Read `CLAUDE.md` §5 before starting.

## Goal
Login, JWT auth (access + refresh), and RBAC middleware enforced on every API route. Frontend login page + protected routing.

## Scope
1. **Backend**
   - `POST /api/v1/auth/login` (`user_id` + password — **never email** — → access + refresh JWT, includes `role`, `tenant_id`, `location_ids` claims). `user_id` is globally unique (CLAUDE.md §5): a `tenants.tenant_code` column plus a migration composing/enforcing `users.user_id` as one global unique constraint were added this phase so the single-field login form can always resolve to exactly one account, even before Phase 03 (tenant creation) or Phase 04 (user creation) exist to populate it through the UI.
   - `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`.
   - `app/core/security.py` — password hashing (bcrypt), JWT encode/decode.
   - `app/core/deps.py` — `get_current_user`, `require_role(*roles)`, `require_tenant_scope` / `require_platform_scope` dependencies that set the Postgres RLS session vars (`app.current_tenant_id` / `app.is_platform_admin`) via `set_config(..., is_local=true)`.
   - Seed a bootstrap `product_owner` user via a management CLI script (`backend/scripts/create_superuser.py`), prompting for a `user_id` (not email) — bare/unprefixed, since product_owner has no tenant_code.
2. **Frontend**
   - `/login` page (responsive, colorful branding per CLAUDE.md §9) — a single **User ID** text field (plain text input, not `type="email"`, no `@` validation) + password field, same form for every role including Product Owner.
   - Auth store (Zustand) + route guards per role; redirect logic: `product_owner` → `/platform`, others → `/pos` or `/dashboard` based on role.
   - Axios interceptor: attach JWT, auto-refresh on 401 once, redirect to login on refresh failure.

## Acceptance Criteria
- Login works for a seeded product_owner and a seeded tenant_admin, both authenticating by `user_id`; wrong role is blocked from platform routes and vice versa.
- Attempting to create two users with the same *composed* `user_id` (i.e. same `tenant_code` + same local handle) is rejected with a clear duplicate error at the database's global unique constraint; two different tenants picking the same local handle (e.g. both wanting "admin01") succeed without colliding, since their composed ids differ by `tenant_code` prefix.
- Token refresh flow verified (expire access token manually, confirm silent refresh).
- All routes from Phase 01 onward require auth by default; explicitly list any public route (this phase's allowlist: `GET /api/v1/health`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`).
