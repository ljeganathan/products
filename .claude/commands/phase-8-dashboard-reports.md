---
description: Phase 8 - Role/plan-aware dashboard, low-stock notification service, reports & exports
---

# Phase 8 — Dashboard, Notifications & Reports

Read `docs/API_CONTRACTS.md §Dashboard, §Notifications & Reports` and
`docs/SUBSCRIPTION_TIERS.md` (dashboard depth differs by plan — this is
enforced the same way as every other gated feature: backend
`feature_enabled()` is the source of truth, frontend just hides/upsells).

## Tasks

### A. Dashboard (backend)

1. `GET /dashboard/summary` — always available to `admin`: today's sales
   total, bill count, average bill value, top 5 items, current low-stock
   count (0 on Lite since that endpoint is gated, not an error).
2. `GET /dashboard/trend`, `GET /dashboard/breakdown` — gated behind
   `feature_enabled(tenant_id, "dashboard_range")` (Pro/Pro Max). Trend
   supports `group_by=day|hour`; breakdown supports
   `by=category|cashier|payment_mode`.
3. `GET /dashboard/stores` — Pro Max only, multi-store consolidated totals
   with per-store drill-down (reuses the `multi_store` feature flag from
   Phase 7).
4. `GET /dashboard/export.pdf` — Pro Max only, renders the current
   dashboard view server-side to PDF (reuse `weasyprint` or similar
   lightweight HTML-to-PDF; keep it in `services/dashboard_export_service.py`).
5. `GET /platform/dashboard` — product_owner only: active tenant count,
   MRR (derived from active subscriptions × plan price), plan mix
   breakdown, tenants trialing/churned this month, overdue invoice count.
   Pulls from `subscriptions`/`plans`/`subscription_invoices` — no new
   tables needed.

### B. Dashboard (frontend)

6. `/dashboard` page (admin's default landing route after login, per
   Phase 4 routing): summary cards (today's sales, bills, top items,
   low-stock count) always visible.
   - **Lite**: cards only, no charts, a visible "Upgrade to Pro for trends
     & breakdowns" banner instead of a blocked/broken chart area.
   - **Pro**: add date-range picker, sales trend chart, category/cashier/
     payment-mode breakdown charts, low-stock widget linking to
     `/stock/low-stock`.
   - **Pro Max**: add store switcher/consolidated toggle, drag-to-reorder
     widgets (persist layout per user), "Export as PDF" button.
7. `/owner/dashboard` — product_owner platform view: tenant count, MRR,
   plan-mix pie/bar chart, churn this month, overdue invoices list with
   click-through to `/owner/subscriptions`.

### C. Low-stock notifications

8. `services/notification_service.py`: APScheduler job (default every 15
   min) scanning `stock` vs `items.reorder_level` per tenant with
   `low_stock_alerts` enabled, creates `notifications` rows with a
   dedup/cooldown window (don't re-notify the same item repeatedly), and
   optionally emails the admin (SMTP/transactional-email interface,
   documented as an extension point like the payment gateway in Phase 7).
9. In-app notification bell (topbar, wired in Phase 4 shell) finished
   end-to-end: mark read/unread, click-through to the relevant stock item.

### D. Reports

10. `GET /reports/sales` (Lite: today-only; Pro/Pro Max: full range),
    `GET /reports/gst-summary`, `GET /reports/sales.csv` (Pro/Pro Max only).
11. `/reports` page: filters, the same chart components used on the
    dashboard (reuse, don't duplicate), export button gated by plan.
12. Scheduled email reports (Pro Max only): daily/weekly APScheduler job
    emailing the owner a dashboard-style summary.

### E. Tests

13. Dashboard gating per plan (Lite gets summary only, Pro gets
    trend/breakdown, Pro Max gets multi-store + export), notification
    dedup logic, report totals correctness against
    `scripts/seed_dev_data.py` fixtures, platform dashboard MRR calculation.

## Definition of Done
- [ ] `/dashboard` shows correct live data for each plan tier with the right depth (verified by switching a demo tenant's plan and reloading)
- [ ] Lite dashboard shows an upgrade banner instead of broken/empty charts
- [ ] Pro Max dashboard store-switcher and PDF export both work
- [ ] `/owner/dashboard` shows correct MRR and plan-mix numbers against seeded subscriptions
- [ ] Low-stock notification fires once per item per cooldown window, not repeatedly
- [ ] Reports page totals match seeded fixtures; CSV export blocked on Lite
- [ ] Scheduled email job verifiably scheduled and Pro-Max-only
