---
description: Phase 3 - Item/category/stock master APIs, tax config, company & printer settings APIs
---

# Phase 3 — Backend Core Domain APIs

Read `docs/DATABASE_SCHEMA.md` and `docs/API_CONTRACTS.md` fully.
Router → Service → Repository → Model layering is mandatory (CLAUDE.md §3).

## Tasks

1. **Categories**: full CRUD, supports `parent_category_id` for FMCG
   sub-categories (e.g. "Dairy" → "Milk", "Curd"). Both `name_en`/`name_ta`
   required.
2. **Items**: full CRUD per `docs/API_CONTRACTS.md §Categories & Items`.
   - Barcode uniqueness enforced per tenant.
   - `GET /items?barcode=` exact match, sub-50ms target (indexed lookup).
   - `POST /items/bulk-import`: CSV template matching FMCG-standard columns
     (name_en, name_ta, category, brand, pack_size, barcode, sku, unit,
     mrp, selling_price, cost_price, tax_profile, hsn_code, reorder_level,
     reorder_qty, opening_stock). Validate and return a row-level error
     report for bad rows rather than failing the whole import.
3. **Stock**: `GET /stock` (joins item + quantity + computed `low_stock`
   boolean using `reorder_level`), `POST /stock/adjust` (writes both
   `stock` and a `stock_movements` row atomically), `GET /stock/movements`.
   `GET /stock/low-stock` gated by `feature_enabled(tenant_id,
   "low_stock_alerts")` from Phase 2 middleware — return 403 with an
   upgrade-plan message on Lite.
4. **Tax profiles**: CRUD, one profile flagged `is_default`; validation that
   `cgst_pct + sgst_pct` (or `igst_pct`) matches a real TN FMCG slab (0, 5,
   12, 18, 28) but allow custom values with a warning field in the response
   rather than hard rejection (some exempt/custom cases exist).
5. **Company settings**: `GET/PATCH /settings/company` including logo
   upload endpoint (`POST /settings/company/logo`, stores to a local
   `/media` volume mounted in Docker Compose, returns `logo_url`; document
   the swap-to-S3-compatible-storage path as a comment for later scale).
6. **Printer profiles**: CRUD, gated by `check_printer_profile_limit` from
   Phase 2. `type` enum drives which template renderer Phase 5 uses later.
7. Tests for each router: happy path, validation errors, tenant isolation,
   plan-limit rejection paths.

## Definition of Done
- [ ] All endpoints in this phase implemented and documented in `docs/API_CONTRACTS.md`
- [ ] Barcode scan-lookup returns in a single indexed query
- [ ] Bulk item import handles a 100-row CSV with 3 intentionally bad rows and reports them clearly
- [ ] Low-stock endpoint returns 403 on Lite plan, 200 on Pro/Pro Max
- [ ] Logo upload works end-to-end and `company_settings.logo_url` resolves to a servable file
- [ ] `pytest` passes for all Phase 3 routers
