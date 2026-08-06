# /phase-04-user-management

Read `CLAUDE.md` §5, §6 before starting.

## Goal
Tenant Admin's user management panel — add/edit/deactivate **Cashier** (`pos_user`), **Waiter**, and **KOT User** (`kitchen` role) accounts, enforcing the seat cap of the tenant's current plan, and setting cashier incentive rates.

## Scope
1. **Backend** (`/api/v1/users/*`, `tenant_admin` role, tenant-scoped)
   - CRUD users within tenant; role assignment restricted to `tenant_admin`, `pos_user`, `waiter`, `kitchen`. The UI presents these as three staff categories — **Cashier / Waiter / KOT User** — `kitchen` is labeled "KOT User" everywhere in UI copy (role dropdown, table filter, badges); the underlying role code stays `kitchen` for backend/API/RLS continuity with Phase 01-02, this is a display-label-only distinction, not a schema change. Admin enters a short local handle (**never email**), unique within the tenant; the API composes and stores the actual login `users.user_id` as `{tenant.tenant_code}-{local_handle}` (CLAUDE.md §5) — globally unique by construction, so the admin never has to worry about colliding with another tenant's staff. Both the local handle and the full composed login id are returned/displayed so the admin can hand the login id to their staff. Set at creation and not user-editable (admin can reset password, not change `user_id`).
   - `incentive_rate` field (%, nullable) on `users`, editable only when role = `pos_user` (cashier) — used by POS/reports to compute per-bill cashier incentive on net sale value (post-discount, pre-tax), same mechanic as waiter incentive in Phase 06/07.
   - Seat-cap enforcement: reject create if `count(active users of billable roles) >= plan.max_users`; return a clear error the frontend can show ("Upgrade to Pro to add more users").
   - Per-location access assignment (relevant now that every tier can have multiple locations, capped per plan per CLAUDE.md §4/§6 — build the join table now, UI shown for all tiers, list limited to that tenant's location count).
   - Password reset (admin-triggered) and account activate/deactivate (soft delete, not hard delete, to preserve order/audit history).
2. **Frontend** (`/admin/users`)
   - Table of users with role badge (**Cashier / Waiter / KOT User / Admin**), status, location(s), incentive rate (cashiers only).
   - Add/Edit modal with role dropdown scoped to allowed roles and labeled with the three staff categories above, local-handle field (plain text, not email-styled — composed login id shown as a read-only preview once a tenant is known), live seat-count indicator ("4 / 6 POS seats used"); incentive-rate % field appears only when role = `pos_user`.
   - Deactivate confirmation dialog (not delete) with clear copy that history is preserved.

## Acceptance Criteria
- Lite-tier tenant blocked from adding a 3rd billable user with a clear upgrade prompt; Pro Max tenant has no cap.
- Deactivated user cannot log in but still appears correctly attributed on historical bills/KOTs.
- Setting a cashier's incentive rate here is immediately reflected in the POS bill summary's cashier incentive line (Phase 07) for bills that cashier rings up next.
- A newly created KOT User can log in and lands only on `/kot` with no other nav item visible; hitting `/pos`, `/dashboard`, or any admin route directly by URL redirects them straight back to `/kot` rather than rendering anything (`router.tsx` scopes `kitchen` to `/kot` alone, `tenant_admin` included on every route).
