# /phase-19-pos-multilocation-seating

Read `CLAUDE.md` §4, §6, §8, §11 before starting.

## Goal
Fix three related multi-location/multi-party gaps found in manual testing: the POS screen had no way to switch locations for a Pro Max tenant with more than one, a table could only ever hold one open order at a time (so a second party sitting at an already-occupied table risked silently repurposing the first party's cart), and the tenant's own Dashboard/Reports had no per-location breakdown despite the backend already supporting multi-location tenants.

## Scope
1. **Seat/party splitting (POS-22)** — nullable `orders.party_label` (varchar(30)) plus a Postgres partial unique index `uq_orders_open_table_party` on (`tenant_id`, `table_id`, `party_label`) WHERE `status='open' AND table_id IS NOT NULL AND party_label IS NOT NULL`, so two open parties at the same table can't collide on the same label while non-seating and single-party orders stay unconstrained. `GET /orders` gains a `table_id` filter. `TableWaiterBar.tsx`'s table picker now checks for existing open orders on tap: zero open orders selects the table immediately (unchanged pre-Phase-19 path); one or more shows a party sub-picker offering "resume Party N" (loads that party's own cart) or "+ New Party" (fresh cart, same table). `POSPage.tsx`'s `handleSelectTable` branches on the picker's result (`direct`/`resume`/`new-party`) accordingly.
2. **Table occupancy is computed, not stored** — `tables.status` was declared on the model/response but never actually written anywhere, so it was permanently stuck at "free". Replaced with `compute_occupied_table_ids()`, computed on read from `orders.status='open'`, so a second party keeps a table occupied after the first party bills out, and the table only reads "free" again once every party has billed.
3. **POS-25 clubbing verification** — `kot_service.send_kot` was already correctly `order_id`-scoped (repeat KOT sends to the same order always land on the same eventual bill); the actual gap was the table picker never offering a "resume this open order" path at all, so re-tapping the same table risked starting a duplicate order. Fixed as a side effect of #1 above; covered by a dedicated regression test (two KOT sends, one bill, both items present).
4. **POS-35 location picker** — POS header gets a location `<select>` next to the hotel name, shown only when the tenant has more than one location; selection persists in `localStorage` so a fixed counter machine doesn't need re-picking on reload. Tables/waiters/open-orders queries are all scoped to the selected location; switching location clears the in-progress draft (table/section/party/waiter) since none of that carries over to a different location's floor plan.
5. **Dashboard/Reports multi-location** — Reports already had a location filter dropdown from an earlier phase. Added the same pattern to the tenant Dashboard's KPI cards (`getDashboardSummary` already accepted `location_id` server-side but nothing passed it) — a "Location" dropdown next to the date heading, shown only when the tenant has more than one location, independent of the existing Pro Max-only Multi-Location Comparison table (which spans every location for a date range regardless of this filter).

## Acceptance Criteria
- A table with zero open orders still selects immediately with no extra step.
- Tapping an occupied table shows "Party N" (resume) options plus "+ New Party"; starting a new party does not touch any other open party's items at that table.
- A table stays occupied until every party seated at it has billed; it only reads "free" again once the last open order there is billed.
- Two KOT sends to the same order followed by one bill produces a single bill containing both sends' items.
- The POS location picker only renders for tenants with more than one location, and the selection survives a page reload.
- Switching POS location clears any in-progress draft rather than carrying a stale table/section selection into the new location.
- The tenant Dashboard's KPI cards can be filtered to a single location, in addition to (not instead of) the existing Pro Max multi-location comparison table.
