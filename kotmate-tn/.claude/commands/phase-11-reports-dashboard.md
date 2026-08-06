# /phase-11-reports-dashboard

Read `CLAUDE.md` §6 before starting.

## Goal
Reports page (sales, item-wise, category-wise, waiter-wise, cashier-wise, waiter/cashier incentive, tax summary, shift/Z-report) with export, and a Dashboard with KPIs/charts.

## Scope
1. **Backend** (`/api/v1/reports/*`, `/api/v1/dashboard/*`, tenant-scoped, date-range and location filterable)
   - Sales summary, item-wise sales, category-wise sales, tax collected summary, daily Z-report/shift close.
   - **Waiter-wise sales report**: net sale value, bill count, and covers per waiter for the date range.
   - **Cashier-wise sales report**: net sale value and bill count per `pos_user` (cashier) for the date range — same shape as waiter-wise, keyed by cashier instead.
   - **Waiter incentive report**: per waiter, net sale value × `incentive_rate` = incentive earned, for the date range, with a grand-total row — this is the payout worksheet for owners running weekly/monthly waiter commission.
   - **Cashier incentive report**: same computation as above, keyed by cashier (`pos_user.incentive_rate`), sourced from bills where that cashier was the cashier-of-record (Phase 07).
   - Both incentive reports reconcile against the informational incentive lines shown live on the POS bill summary (Phase 07) — same net-sale-value (post-discount, pre-tax) basis, so a manager can trust the report matches what staff saw bill-by-bill.
   - Export: CSV for all tiers with report access (Pro+); PDF/Excel export for Pro Max (reuse a shared export service, e.g. pandas/openpyxl for xlsx, reportlab or a simple HTML-to-PDF for pdf).
   - Dashboard KPIs: today's sales, bill count, average bill value, top items, hourly sales trend; multi-location comparison view for Pro Max.
2. **Frontend** (`/reports`, `/dashboard`)
   - Report list with date-range picker, filter, export buttons gated by plan; waiter-wise, cashier-wise, waiter incentive, and cashier incentive appear as four distinct report entries (not one merged "staff" report) since owners typically review/pay these separately.
   - Dashboard with KPI cards + charts (recharts), Lite gets basic KPI cards only per CLAUDE.md §6, Pro+ gets charts.

## Acceptance Criteria
- Report totals reconcile exactly against Phase 09 bill data for a given date range (cross-check with a manual SQL sum).
- Waiter incentive report and cashier incentive report totals match the sum of the live incentive lines shown on each bill's POS summary at the time it was billed (Phase 07).
- A bill with both a waiter and a cashier assigned appears correctly in both incentive reports without double-counting the sale itself (sales figures aren't summed across the two reports).
- Export files open correctly and match on-screen figures.
- Feature gating verified: Lite sees basic KPIs only, no export; Pro sees charts + CSV; Pro Max sees everything + multi-location comparison.
