# /phase-10-settings-hotel-master

Read `CLAUDE.md` §6, §9, §10 before starting.

## Goal
Central Settings page tying together the Company Master (hotel locations, capped per plan), category settings, printer settings, tax settings, and Hotel Master (with logo + QR/UPI id) per location.

## Scope
1. **Backend** (`/api/v1/settings/*`, `tenant_admin`)
   - `hotel_master`: name, Indian-format address (`door_no`, `street`, `city`, `district`, `state` enum, `pincode` 6-digit — CLAUDE.md §8/§9, not a single free-text field), phone, GSTIN, logo upload (reuses Phase 05 storage service), UPI id for QR generation, `show_tamil_names` toggle (this is the switch read by POS **print output only** — the POS staff-facing grid always shows English+Tamil together regardless, per CLAUDE.md §9) — one row per `tenant_location`.
   - GSTIN validation: derive the expected state code from GSTIN's first 2 digits and confirm it matches the selected `state`; warn (don't hard-block) on mismatch since data entry order can vary.
   - Printer settings CRUD (KOT printer + Bill printer, can differ) — type (thermal/dotmatrix), connection details, scoped per location.
   - Tax settings CRUD (ties to Phase 09 `tax_rules`; CGST/SGST kept as distinct rate rows, never merged), scoped per location.
   - Company Master / Locations (`/api/v1/locations/*`, all tiers): add/edit/deactivate `tenant_locations` (name, Indian-format address — same fields as `hotel_master` above), each getting its own `hotel_master`, printers, and tax rules. Enforce the plan cap server-side (Lite=1, Pro=2, Pro Max=5 — CLAUDE.md §4/§6) with a clear "Upgrade to add another location" error once reached. Location switcher in the UI header once a tenant has more than one.
2. **Frontend** (`/admin/settings`)
   - Tabbed settings page: General (Hotel Master + logo + QR/UPI + Tamil-on-print toggle, per selected location), Printers, Tax, Categories (links to Phase 05 page), Locations (visible on all tiers; "Add Location" button disables with an upgrade note once the plan cap is reached instead of the tab being hidden).
   - Address form uses the Indian layout — Door No./Building, Street/Area, City, District, State (dropdown of Indian states/UTs), 6-digit PIN Code (numeric, validated) — for both Company Master and per-location Hotel Master (CLAUDE.md §9).
   - Logo upload with live print-preview thumbnail.

## Acceptance Criteria
- Toggling `show_tamil_names` off immediately hides Tamil names on the **printed** KOT/bill templates (no reload needed, or a documented reload requirement if simpler) — it must NOT hide Tamil names on the live POS screen grid, which always shows both languages.
- A Lite tenant sees the Locations tab but cannot add a 2nd location (upgrade prompt); a Pro tenant can add a 2nd but not a 3rd; a Pro Max tenant can add up to 5, each with independent printers/tax rules.
- Entering a GSTIN whose embedded state code doesn't match the selected State shows a warning, not a hard block.
- Logo appears correctly on a simulated bill print, for the currently selected location.
