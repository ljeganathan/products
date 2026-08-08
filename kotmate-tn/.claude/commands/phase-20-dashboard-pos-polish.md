# /phase-20-dashboard-pos-polish

Read `CLAUDE.md` §6, §9, §11 before starting.

## Goal
Close out the manual-testing backlog: replace the tenant Dashboard's "Top Item" KPI box (redundant with the "Top Selling Items" list right below it) with a "Low Stock Items" widget that's actually actionable for a manager glancing at the dashboard, and do a review pass confirming the POS screen already matches CLAUDE.md §9's design language after Phases 18-19's functional fixes landed.

## Scope
1. **Dash-33a — Low Stock Items widget.** No backend endpoint existed for a tenant-wide low-stock list (only per-item KOT/POS badges, driven by a websocket push, existed before this phase). Added:
   - `LOW_STOCK_THRESHOLD = 5` promoted from a private constant in `kot_service.py` to a shared one in `item_service.py` (both KOT/POS badges and the new widget now agree on one definition), plus `list_low_stock_items()` — items where `track_inventory=true AND available_qty <= 5`, tenant-wide (items aren't location-scoped), ordered by `available_qty` ascending.
   - `GET /api/v1/dashboard/low-stock-items` (`backend/app/api/v1/dashboard.py`), same access rule as `/summary`, no `location_id` param since stock isn't tracked per-location.
   - Frontend: `getLowStockItems()` in `dashboardApi.ts`; `DashboardPage.tsx`'s KPI row drops the "Top Item" card (3 cards now, not 4); a new `LowStockSection` renders next to "Top Selling Items" (side-by-side on `lg:`, stacked below it on narrower widths) showing each low-stock item's name (+ Tamil name) and remaining count, "Out of stock" in red (`text-chili`) for zero, gold (`text-gold`) otherwise, and a plain-language empty state when nothing is low.
2. **POS-38 — design-language review pass.** Audited the already-functional POS screen against CLAUDE.md §9 rather than redesigning from scratch (Phases 18-19 already fixed the functional bugs this was blocked on): dense responsive item grid (`grid-cols-2` → `lg:grid-cols-5`), Meals/Thali oversized combo tiles (`items.is_combo_tile`, set via an Item Master toggle, rendered as a `col-span-2` gold-bordered card in `ItemCard.tsx`), UPI-first payment ordering in `BillingModal.tsx`, table-number-as-dominant-anchor in `CartPanel.tsx`'s cart header, and Indian ₹ formatting (`formatINR` in `lib/utils.ts`, `Intl.NumberFormat("en-IN", ...)` with paise shown only when non-zero) were all confirmed already in place from earlier phases — no changes needed, verified by direct code read plus a manual spot-check per the checklist below.
3. **Incidental fix — `search_items` bind-parameter bug.** While running the full regression suite for this phase, `test_items.py::test_fuzzy_search_endpoint_tolerates_typos` and `test_search_matches_short_realistic_prefix` failed with `sqlalchemy.exc.InvalidRequestError: A value is required for bind parameter 'q'` — a pre-existing defect unrelated to this phase's scope, caused by two separate `text()` clauses both named `:q` bound via an outer `.params(q=q)` on the `Select`, which SQLAlchemy's statement-plan caching resolved unreliably. Fixed by binding each `text()` fragment directly via `.bindparams(q=q)` instead. Also removed a self-contradictory duplicate assertion (`assert "Filter Coffee" not in names` immediately after asserting the opposite) left over in the second test.

## Acceptance Criteria
- Dashboard KPI row shows exactly 3 cards (no "Top Item").
- Low Stock Items widget lists tracked items at ≤5 stock, lowest first, with "Out of stock" styled distinctly at 0; shows a clear empty state when nothing qualifies.
- Toggling an item's `track_inventory`/`available_qty` in Item Master is reflected in the Low Stock widget on next Dashboard load (no live push needed here, unlike the KOT/POS websocket badges).
- POS item grid, combo tiles, payment ordering, cart table-number sizing, and ₹ formatting all match CLAUDE.md §9 on manual inspection — confirmed already-correct, not regressed.
- `search_items` (`GET /api/v1/items/search`) returns correct results for both typo and short-prefix queries; `test_items.py` passes in full.
