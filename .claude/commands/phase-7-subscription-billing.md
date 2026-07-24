---
description: Phase 7 - Product owner console, plan management, feature gating end-to-end
---

# Phase 7 — Subscription, Billing & Product Owner Console

Read `CLAUDE.md §4 and §6`, `docs/SUBSCRIPTION_TIERS.md`, and
`docs/API_CONTRACTS.md §Platform / Product Owner`.

## Tasks

1. **Product owner console** (`/owner/*`, product_owner role only):
   - **Tenants**: list all tenants, view status/plan/usage (users, stores,
     printer profiles vs their limits), suspend/reactivate a tenant.
   - **Dashboard** (`/owner/dashboard`): active tenant count, MRR, plan-mix
     breakdown, churn this month, overdue invoices — full implementation
     lands in Phase 8 (`GET /platform/dashboard`); wire the nav entry and a
     basic placeholder view now so Phase 8 only needs to fill it in.
   - **Plans**: view/edit the 3 plans (name, price, limits, features_json)
     — this is how the product owner changes pricing/limits without a code
     deploy, per `CLAUDE.md §4`.
   - **Subscriptions**: view/change a tenant's plan, add extra-user/
     extra-store add-ons, view billing period, manually mark an invoice
     paid (manual/offline payment flow for v1 — see note below).
   - **Invoices**: list `subscription_invoices`, generate the next period's
     invoice, mark paid/overdue.
   - **Maintenance**: a simple global maintenance-mode toggle + message
     banner (stored in a `platform_settings` table/row) that the frontend
     shell checks on load and shows a maintenance banner/blocking screen
     for tenant users (not for product_owner) when enabled.
2. **Payment integration note**: implement the invoice/subscription data
   model and manual "mark as paid" flow fully working end-to-end first.
   Stub the `razorpay_subscription_id` field and add a
   `services/payment_gateway_service.py` with a clearly documented
   interface (`create_subscription`, `verify_webhook`, `cancel`) that can
   be implemented against Razorpay (recommended for Indian SaaS/UPI
   support) in a later iteration — do not fabricate a fake working gateway
   integration; this must be a real, clean extension point.
3. **End-to-end feature gating verification**: build (or extend) an
   integration test suite that, for each plan tier, walks through: user
   creation up to and beyond the limit, low-stock alert access,
   multi-store access, discount rule creation, API access — confirming the
   backend `plan_limits` middleware (Phase 2) and the frontend upgrade-CTA
   patterns (Phase 6) agree with `docs/SUBSCRIPTION_TIERS.md`.
4. **Tenant-side subscription view**: admin-facing `/settings/subscription`
   showing current plan, usage vs limits, and an "upgrade" flow that (in
   this manual-payment v1) creates a pending plan-change request visible to
   the product owner console.

## Definition of Done
- [ ] Product owner can view all tenants and their current usage vs plan limits
- [ ] Changing a tenant's plan immediately changes what that tenant's users can access
- [ ] Downgrade is blocked with a clear message when current usage exceeds target plan limits
- [ ] Maintenance-mode banner appears for tenant users and not for product_owner
- [ ] Full plan-tier feature matrix from `docs/SUBSCRIPTION_TIERS.md` is verified by an automated test
- [ ] Payment gateway interface exists, documented, not faked as "working"
