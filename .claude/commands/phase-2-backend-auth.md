---
description: Phase 2 - Auth, JWT, roles, tenant middleware, plan-limit middleware
---

# Phase 2 — Backend Auth & Core Middleware

Read `CLAUDE.md` §5 (Role Matrix) and `docs/API_CONTRACTS.md §Auth` before
starting.

## Tasks

1. `core/security.py`: password hashing (bcrypt via passlib), JWT
   create/verify for access + refresh tokens, embedding
   `{user_id, tenant_id, store_id, role}` in the access token payload.
2. `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`,
   `GET /auth/me` per `docs/API_CONTRACTS.md`.
   - `product_owner` login does not require a `tenant_id` (platform-level
     account); token has `tenant_id: null` and `role: product_owner`.
3. `middleware/tenant_context.py`: FastAPI dependency that extracts
   `tenant_id`/`store_id`/`role` from the verified JWT and makes them
   available to every route via `Depends`. Raise 403 if a non-product_owner
   token has no `tenant_id`.
4. `middleware/rbac.py`: `require_role(*roles)` dependency factory used to
   guard routers per the Role → Access Matrix in `CLAUDE.md §5`.
5. `middleware/plan_limits.py`: loads the tenant's active plan +
   subscription, exposes helper functions:
   - `check_user_limit(tenant_id)` — raise 402/403 if adding a user would
     exceed `plans.max_users` (+ `extra_users` add-ons).
   - `check_store_limit`, `check_printer_profile_limit`.
   - `feature_enabled(tenant_id, feature_key)` — e.g. `low_stock_alerts`,
     `multi_store`, `dashboard_range`, `discount_rules_advanced`,
     `api_access` — reads `plans.features_json`.
   These are called from the relevant Phase 3/5/6/7 routers — wire the
   functions now, they get consumed later.
6. `POST /users` (create) and `GET/PATCH/DELETE /users/{id}` with RBAC
   (`admin` only, scoped to own tenant) and `check_user_limit` enforcement.
7. Audit logging: a small `services/audit_service.py` that writes to
   `audit_logs` on login, user create/deactivate, and plan changes (hook
   points only for plan changes; full use in Phase 7).
8. Tests: `backend/app/tests/test_auth.py` covering login success/failure,
   token refresh, role guard rejection, tenant isolation (user from tenant
   A cannot fetch tenant B's data), and user-limit enforcement at the plan
   boundary.

## Definition of Done
- [ ] Login returns valid access+refresh tokens for product_owner/admin/pos_user
- [ ] Protected routes reject missing/invalid/expired tokens with 401
- [ ] Role guard rejects wrong-role access with 403
- [ ] Tenant isolation verified by test (cross-tenant fetch fails)
- [ ] Adding a user beyond `plans.max_users` is blocked with a clear error
- [ ] `pytest` passes for all auth/rbac/plan-limit tests
