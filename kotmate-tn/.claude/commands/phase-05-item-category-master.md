# /phase-05-item-category-master

Read `CLAUDE.md` §6, §8, §9 before starting.

## Goal
Category master and Item master, with Tamil name field, image upload (Pro/Pro Max only), top-seller flagging that feeds the POS screen's "Top Selling" category tab, and per-seating-section price overrides (Pro/Pro Max).

## Scope
1. **Backend** (`/api/v1/categories/*`, `/api/v1/items/*`, tenant-scoped)
   - Category CRUD: `name_en`, `name_ta`, `display_order`, `is_active`.
   - Item CRUD: `name_en`, `name_ta`, `category_id`, `price` (the base/default price), `tax_class_id`, `image_url` (nullable — reject upload attempt with 403 + upgrade message if tenant plan lacks `item_images`), `item_code` (short, optional, unique per tenant — printable on a counter menu card for POS numeric quick-entry per CLAUDE.md §9), `is_top_seller`, `is_combo_tile` (flags meals/thali-style combos that POS renders as an oversized tile — CLAUDE.md §9), `track_inventory` (bool, default false), `available_qty` (int, nullable — only meaningful when `track_inventory` is true), `is_active`.
   - `PATCH /api/v1/items/{id}/restock` — sets `available_qty` directly (tenant_admin only); this is the only way the count changes upward, since there's no automatic restock/reset (CLAUDE.md §11). Toggling `track_inventory` off clears `available_qty` back to null rather than leaving a stale count hidden behind a disabled flag.
   - `item_section_prices` sub-resource: `GET/PUT /api/v1/items/{id}/section-prices` — list/set a price per `seating_section_id` for that item; omitting a section means it falls back to the item's base `price`. Reject writes with 403 + upgrade message if tenant plan lacks `section_pricing` (Lite).
   - Image upload endpoint: validate size/type, store under `/uploads/{tenant_id}/items/`, return URL; abstract storage behind an interface (`app/services/storage.py`) so swapping to cloud storage later is a one-file change.
2. **Frontend** (`/admin/categories`, `/admin/items`)
   - Category list with drag-to-reorder (`display_order`), add/edit modal (EN + TA fields side by side).
   - Item list (searchable, filter by category), add/edit modal with EN/TA name fields, base price, item code, category picker, image upload (hidden entirely with an "Upgrade to Pro" note on Lite), top-seller toggle, "Combo/Thali tile" toggle, a "Track stock count" toggle that reveals an `available_qty` number input + a one-tap "Restock" action (available on every tier — this is soft awareness, not a plan-gated feature).
   - Per-section price override editor inside the item edit modal (Pro/Pro Max only, hidden with an "Upgrade to Pro" note on Lite): one row per seating section with an optional price input — blank row means "use base price"; this is deliberately per-item, not a blanket "+X% for AC" markup, since owners typically only reprice a subset of items (e.g. mains) while leaving others (drinks/desserts) flat.
   - Bilingual field labels clearly marked (e.g. "Item Name (English)" / "பொருள் பெயர் (தமிழ்)").

## Acceptance Criteria
- Lite tenant cannot upload item images or set section price overrides (UI hides both, API rejects both); Pro/Pro Max can.
- Items created here immediately appear in a quick manual check against the POS item-search endpoint stub (full POS UI comes in Phase 07).
- Setting an override for one section (e.g. AC) changes only that section's resolved price for the item; other sections and the default/base price are unaffected.
- Tamil names render correctly (UTF-8 end-to-end, font supports Tamil glyphs in both admin UI and later print templates).
- Toggling `track_inventory` off and back on clears any prior `available_qty` rather than resurrecting a stale count; `PATCH /restock` is rejected on an item with `track_inventory=false`.
