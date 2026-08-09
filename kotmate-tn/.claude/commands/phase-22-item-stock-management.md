# /phase-22-item-stock-management

Read `CLAUDE.md` §6, §8, §11 before starting. This extends the existing Item Master (Phase 05) and KOT screen (Phase 08) soft-inventory feature — it does not add a separate module.

## Goal
Add an audit ledger for every `items.available_qty` change, a tenant-level Pro/Pro Max-gated on/off switch layered on top of the existing (always-on, every-tier) low-stock badges, and a new "Stock Management" tab on the KOT screen for bulk-managing quantities — without changing anything about how Lite tenants already use stock tracking today.

## Scope
1. **Data model** — new `stock_ledger` table (`item_id`, `location_id` nullable, `change_qty` signed, `reason` ∈ `manual_set`/`kot_deduction`/`restock`, `reference_order_id`/`reference_bill_id` nullable) and `tenants.stock_management_enabled` (bool, default false). Two migrations: schema (`5d52cf46dd81`), and a data-only JSONB merge adding `stock_management: true` to the `pro`/`pro_max` plan rows' `features` (`ffa2fb832bd7`).
2. **`backend/app/services/stock_service.py`** (new) — `has_stock_management_feature(plan_features)` (plan-tier gate alone, used for the new Stock Management tab endpoints and the Settings toggle-write endpoint); `is_stock_tracking_enabled(tenant, plan_features)` (the Lite-inclusive **effective** flag — returns `True` unconditionally when the plan doesn't have `stock_management` at all, since that predates plan-gating and must keep working exactly as before for Lite; only Pro/Pro Max tenants have `tenant.stock_management_enabled` actually gate anything); `set_item_stock(...)` (the one place that mutates `available_qty` and writes the matching `StockLedger` row — reused by manual edits, restock, and KOT-send deduction); `list_stock_items(...)` (every active item, any tracking state, for the new tab).
3. **New `GET/PATCH /api/v1/stock/items`** router — the Stock Management tab's backend, gated on `has_stock_management_feature` + `tenant.stock_management_enabled` (both required — Lite and toggle-off both 403). Setting a quantity here also turns `track_inventory` on for that item (one action).
4. **Existing write paths refactored to log**: `item_service.restock_item()` (now `reason="restock"`) and `update_item()`'s `available_qty`-changing branch (`reason="manual_set"`) both route through `set_item_stock` instead of a bare `setattr`.
5. **`kot_service.send_kot()`** — the existing KOT-send deduction is now gated on `is_stock_tracking_enabled` (not just `item.track_inventory` alone) and writes a `kot_deduction` ledger row with `reference_order_id`/`location_id` set, atomically with the ticket (same transaction, same route-level commit as before).
6. **`MeResponse.stock_tracking_enabled`** (new field, `/auth/me`) — the single computed flag every frontend surface checks: POS `ItemCard.tsx` badges, the KOT screen's low-stock banner, and Item Master's "Track stock count" checkbox editability.
7. **Settings** — new `PATCH /api/v1/settings/stock-management` (tenant_admin, 403 if the plan lacks the feature) and a new "Stock" tab in `SettingsPage.tsx` (visible only when `meData.features?.stock_management === true`) with a single checkbox mirroring the existing `show_tamil_names` toggle pattern.
8. **KOT screen** — `KotDisplayPage.tsx` gains a `"tickets"|"stock"` tab strip, shown only when `meData.features?.stock_management === true` (Lite keeps its single un-tabbed board); new `StockManagementTab.tsx` (category-grouped, searchable, per-row qty input + Save) and `stockApi.ts`.
9. **Item Master** — `ItemsPage.tsx`'s "Track stock count" checkbox and the dedicated "Restock" row action both gate on `meData.stock_tracking_enabled`, with an explanatory hint when disabled.
10. **Dashboard Low Stock widget** (Phase 20) — gated server-side on the same effective flag, returning an empty list rather than a 403 when off (a quiet widget, not an error).

## Acceptance Criteria
- Lite tenants: zero behavior change anywhere — Item Master checkbox always editable, no Settings "Stock" tab, no KOT tab strip, badges/decrement work exactly as before this phase, including the new ledger silently recording their changes too.
- Pro/Pro Max tenants: the tenant switch defaults off; while off, badges/decrement/Dashboard widget are all empty and the Stock Management tab's endpoints 403 with a clear message, but the tab strip itself still renders (plan-gated, not toggle-gated) so an admin can find the toggle's location via Settings.
- Turning the switch on immediately restores whatever `track_inventory`/`available_qty` was already configured — nothing is ever cleared by disabling.
- Every `available_qty` change (manual edit, dedicated restock, KOT-send deduction, Stock Management tab save) writes exactly one `stock_ledger` row with the correct `reason`; KOT-send deduction is atomic with the ticket (same transaction/commit).
- Entering a quantity in the Stock Management tab for a previously-untracked item turns tracking on for it.
