---
description: Phase 6 - Stock entry UI, category/item UI, settings UI, low-stock alerts UI
---

# Phase 6 — Stock, Master Data & Settings UI

Read `docs/API_CONTRACTS.md §Categories & Items, §Stock, §Tax & Settings`.
All screens live under the `admin`-facing `AppLayout` (Phase 4).

## Tasks

1. **Category master** (`/categories`): tree/list view supporting
   parent/child FMCG categories, add/edit modal with `name_en`/`name_ta`.
2. **Item master** (`/items`): paginated searchable table with FMCG columns
   (barcode, name, category, brand, pack size, MRP, selling price, tax
   slab, stock on hand, reorder level). Add/edit form includes a barcode
   field with a "scan to fill" mode (reuses the barcode-capture logic from
   Phase 5). Bulk CSV import UI with the row-level error report from the
   Phase 3 API.
3. **Stock entry & availability** (`/stock`): table view of all items with
   current quantity, computed availability status (in-stock / low-stock /
   out-of-stock badge), manual stock adjustment modal (reason required:
   purchase/adjustment/return/damage), and a movements history drill-down
   per item.
4. **Low-stock notifications UI** (Pro/Pro Max): a notification bell in
   `AppLayout` topbar polling `GET /notifications`, a dedicated
   `/stock/low-stock` view; on Lite plan, this entry point shows an
   "Upgrade to Pro" empty state instead of a 403 error page.
5. **Settings pages** under `/settings`:
   - **Category/Item quick links** (reuse above).
   - **Tax settings**: manage `tax_profiles`, mark default, TN CGST/SGST
     slab presets selectable + custom override.
   - **Printer settings**: manage `printer_profiles`, a "Test Print" button
     that sends a sample payload through the Phase 5 print dispatch logic.
   - **Company master**: legal name, display name, address, GSTIN, FSSAI
     no., phone, logo upload (with live thermal-receipt header preview),
     invoice footer text.
   - **Language settings**: sets the tenant/user default language used
     across stock/POS screens (per `CLAUDE.md §7`).
6. **Discount rules UI** (Pro+): manage item/category/bill discount rules
   with an active-date range; Lite sees an upgrade prompt.

## Definition of Done
- [ ] Item + category CRUD fully functional with Tamil/English fields
- [ ] Barcode "scan to fill" works in the item form using the same scanner
- [ ] CSV bulk import UI surfaces row-level errors clearly
- [ ] Stock adjustment writes visible immediately in availability view
- [ ] Low-stock UI correctly gated by plan (Lite blocked with upgrade CTA, Pro/Pro Max functional)
- [ ] Company settings logo appears correctly in the Phase 5 print preview
- [ ] Test Print button produces a correctly formatted sample on both thermal and dot-matrix profiles
