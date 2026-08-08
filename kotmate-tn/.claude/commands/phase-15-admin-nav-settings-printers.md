# /phase-15-admin-nav-settings-printers

Read `CLAUDE.md` §9, §10 before starting.

## Goal
Clean up tenant_admin console navigation (dead placeholder links, no consistent way back to Dashboard), move Printers/Tax quick-add into Settings instead of forcing a page navigation, and extend printer specs with paper width + WiFi/Bluetooth connectivity.

## Scope
1. **Navigation** (`AppShell.tsx`, `router.tsx`)
   - Delete the dead `NAV_ITEMS = ["items", "waiters"]` placeholder block (both the desktop `<span>` entries and the now-pointless mobile bottom nav, which only ever rendered that same list).
   - `AppShell` now wraps every tenant-scoped admin/reports/billing screen (all `/admin/*` masters, `/reports`, `/billing/history`), not just `/dashboard` — giving every one of those pages the same persistent sidebar instead of an ad-hoc `← Dashboard` text link. Each of those ~12 page components has that per-page breadcrumb link removed (and its now-unused `Link` import, except `SettingsPage.tsx` which still uses `Link` elsewhere).
   - Sidebar gains a "Dashboard" entry (for `tenant_admin`/`pos_user`) and a small icon per nav item.
2. **Settings restructure** (`SettingsPage.tsx`)
   - Printers and Tax Rules tabs change from a "go to the full page" card to an inline quick-add: a compact list + "+ Add" button that opens the same `PrinterFormModal`/`TaxRuleFormModal` used on the dedicated `/admin/printers`/`/admin/tax-rules` pages (now exported for reuse), plus a "Manage all →" link to that full page for editing/deactivating.
   - Categories tab removed entirely — it was a pure duplicate entry point to the already-complete `/admin/categories` page.
3. **Printer specs** (backend `printers` table/schema, `PrinterFormModal`)
   - New `paper_width_mm` column (nullable int). UI offers 58mm/80mm/241mm presets (2"/3" thermal, 9.5" dot-matrix) plus a free-entry "Custom" option — not a CHECK constraint, since real hardware varies.
   - `connection_type` gains `wifi` and `bluetooth` alongside the existing network/usb/local_agent. Connection-specific fields (IP+port for network/wifi, paired device name for bluetooth) are stored in the existing unstructured `connection_details` JSON column and shown/hidden in the form based on the selected connection type.

## Acceptance Criteria
- Every `/admin/*`, `/reports`, and `/billing/history` page shows the same persistent sidebar (with a working Dashboard link) instead of a text-only breadcrumb.
- No dead "Items"/"Waiters" nav entries remain anywhere.
- From `/admin/settings` → Printers tab, adding a printer via "+ Add" does not navigate away from Settings; the new printer appears in both the Settings quick-list and the full `/admin/printers` table.
- Same for Tax Rules.
- Settings has no "Categories" tab.
- Creating a printer with connection type WiFi or Bluetooth succeeds, stores the connection-specific fields, and a paper width (preset or custom) persists and displays correctly.
