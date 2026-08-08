# /phase-14-invoicing-dashboard-alerts

Read `CLAUDE.md` §5, §7, §8 before starting. Depends on Phase 13's `tenants.email`/`phone` migration landing first.

## Goal
Give the Product Owner a way to invoice tenants for their subscription and see, at a glance on the platform dashboard, which subscriptions are expiring/expired and which invoices are overdue.

## Scope
1. **Backend** (`/api/v1/platform/*`, `product_owner` only)
   - New `invoices` table: `tenant_id`, `subscription_id` (nullable), `invoice_number` (server-generated `INV-{YYYYMM}-{seq}`, unique), `amount`, `status` (draft/sent/paid/overdue), `issued_date`, `due_date`, `paid_date`, `description`. Single flat amount, no line items — `plans` are flat-priced. RLS-enabled like every other tenant-scoped table (this table postdates the original RLS migration, so it needs its own enable/force/policy statements).
   - `POST /platform/invoices` — manual create (sets status `sent` immediately, no separate draft→send step for this MVP).
   - `GET /platform/invoices?tenant_id=&status=` — filtered list.
   - `GET /platform/invoices/overdue` — `status != 'paid' AND due_date < today`.
   - `PATCH /platform/invoices/{id}/mark-paid` — sets `status=paid`, `paid_date=today`.
   - `GET /platform/dashboard/alerts` — `{expiring_subscriptions, overdue_invoices}`. Expiring = active subscriptions with `current_period_end` within 7 days or already past. `overdue` is computed on every read from `due_date`, never persisted to the `status` column — no cron job that can silently stop running.
2. **Frontend**
   - `PlatformDashboardPage.tsx` — two new alert cards below the existing 4 KPI cards, each row linking to the tenant's detail page.
   - New `InvoicesPage.tsx` (`/platform/invoices`, linked from `PlatformShell` nav) — create-invoice form (tenant picker, amount, due date, description), status filter chips, list table with a "Mark Paid" action.

## Acceptance Criteria
- Creating an invoice for a tenant immediately appears in the invoice list and, once its due date passes unpaid, in both `GET /invoices/overdue` and the dashboard's Overdue Invoices card — without any manual status change.
- Marking an invoice paid removes it from the overdue views and stamps `paid_date`.
- A subscription within 7 days of `current_period_end` (or already past it) appears in the dashboard's Expiring/Expired Subscriptions card, showing days remaining (negative once expired).
- All of the above verified by an automated test (`tests/test_invoicing.py`) in addition to manual UI testing.
