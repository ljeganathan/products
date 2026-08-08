# /phase-16-item-master-overhaul

Read `CLAUDE.md` §6, §9, §11 before starting.

## Goal
Close the gaps in Item Master surfaced by manual testing: no CSV import/export despite the plan matrix promising it, image/section-pricing only reachable after a save-then-reopen round trip, no way to set an item's tax class from the UI, no deactivate control, and a per-section-price editor whose per-row Save buttons read as data loss even though the API was never actually losing data.

## Scope
1. **Backend** (`/api/v1/items/*`, `tenant_admin` writes / broad reads)
   - `GET /items/export.csv` — plan-gated on `features.item_export` (Pro+), streams `item_code,name_en,name_ta,category,price,tax_class,is_top_seller,is_combo_tile` (no image column, by design — images stay a per-item upload).
   - `POST /items/import.csv` — plan-gated on `features.item_import` (Pro Max only), upserts by `item_code` (blank/unmatched code creates a new item), resolves `category`/`tax_class` by name within the tenant, returns `{created, updated, errors}` with per-row error messages for unresolvable categories/tax classes or invalid prices rather than failing the whole file.
2. **Frontend** (`ItemsPage.tsx`)
   - Add-item flow: the first successful Save in "add" mode no longer closes the modal — it flips the same modal into an in-place edit of the newly created item, so Item Image upload and Per-Section Price Override become available without reopening (previously gated on `editingItem &&`, meaning add mode never saw them at all).
   - Modal layout: core fields → their own Save button → Item Image → Per-Section Price Override → final Done/Cancel row, so image/pricing sit above the closing action instead of below it.
   - `item_code` prefills with the next sequential numeric code (still freely editable).
   - Client-side image size cap (1MB) with an inline error, on top of the existing server-side ceiling.
   - Image preview renders immediately on file selection (local object URL) rather than only after the upload round-trip completes.
   - Item list gains a Status column + Deactivate/Reactivate action (backend `is_active` already existed, just wasn't exposed).
   - Per-Section Price Override changes from N per-row Save buttons (each firing its own PUT) to one "Save All Section Prices" button sending the whole draft set in a single PUT, with a per-row "Saved ✓" indicator that clears as soon as that row is edited again — the API already merged partial updates correctly, this was purely a UX-clarity fix.
   - New Tax Class dropdown (sourced from the tenant's `tax_rules`) — `items.tax_class_id` already existed server-side, wasn't exposed in the form.
   - Export CSV / Import CSV buttons in the page header, shown only when the tenant's plan includes that feature.

## Acceptance Criteria
- Lite tenant: no Export/Import buttons. Pro tenant: Export only. Pro Max tenant: both.
- Adding a new item: Save creates it and immediately reveals Image + Section Pricing in the same modal, no reopen needed.
- Item code field is pre-populated but editable.
- Uploading a >1MB image is rejected client-side with a clear message before any request fires.
- Editing two different sections' prices and clicking "Save All Section Prices" persists both without clearing any other section's existing override (verified against `item_section_prices` directly, not just the UI).
- Deactivating an item flips `is_active` and is reflected immediately in the list (dimmed row, Status badge).
- A CSV with one row matching an existing `item_code` and one new row creates exactly one item and updates exactly one, with row-level errors reported (not a hard failure) for a row referencing an unknown category.
