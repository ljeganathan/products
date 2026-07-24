---
description: Phase 5 - Full POS screen (keyboard + barcode + touch), cart, tax/discount engine, bill save/print
---

# Phase 5 — POS Module (core of the product)

This is the highest-stakes phase — read `docs/API_CONTRACTS.md §POS /
Billing`, `docs/DATABASE_SCHEMA.md §bills/bill_items`, and
`docs/ARCHITECTURE.md §Printer strategy` fully before starting.

## Tasks

1. **Layout**: `/pos` uses `PosLayout` (full-screen, no browser chrome
   distractions). Three zones: item search/entry (top), cart/line-items
   (center, large touch-friendly rows), summary + actions (right or bottom
   panel — pick based on tablet vs desktop breakpoint).
2. **Item entry — three input paths, all wired to the same
   add-to-cart function**:
   - **Barcode scanner**: scanners act as keyboard-emulation (HID) devices
     — capture rapid sequential keystrokes ending in Enter into a hidden
     always-focused input, debounce-detect "scan speed" typing vs a human
     typing an item code, and auto-submit on scanner Enter.
   - **Manual item code / SKU entry**: a visible input, Enter key submits.
   - **Fast search**: type-ahead search box (name_en/name_ta/sku/barcode),
     keyboard arrow-navigable results, Enter/click adds to cart. Use the
     item cache from TanStack Query (Phase 4) for instant local filtering,
     falling back to `GET /pos/items/search` for larger catalogs.
3. **Full keyboard shortcut map** (document these in an in-app "?" help
   overlay, e.g. `F1`):
   - `F2` focus fast-search, `F3` focus barcode/manual entry
   - `F4` apply bill discount, `F5` apply item discount on selected line
   - `+`/`-` or `Ctrl+↑`/`Ctrl+↓` adjust qty on selected cart line
   - `Delete` remove selected line, `Ctrl+Z` undo last removal
   - `F8` hold bill, `F9` recall held bill (opens saved-bill search)
   - `F10` or `Ctrl+Enter` finalize & print
   - `Esc` cancel current bill (with confirm)
   - All shortcuts must also have an equivalent touch/mouse button visible
     on-screen — never keyboard-only.
4. **Cart & totals engine** (client renders live preview, server is
   authoritative on submit):
   - Line items show qty, unit price, line discount, tax slab, line total.
   - Bill-level discount input (flat ₹ or %).
   - Live subtotal → discount → CGST/SGST breakdown (per TN rule,
     configurable, from `tax_profiles`) → round-off → grand total.
   - `POST /bills` on finalize; **never trust client-computed totals** —
     backend in `services/billing_service.py` recomputes from item +
     tax_profile + discount_rule data server-side and is the value actually
     persisted and printed.
5. **Hold / Resume**: `POST /bills/{id}/hold` stores a cart snapshot with
   `status=held`; `F9` opens a quick list of held bills for the current
   cashier to resume.
6. **Saved bill search**: a slide-over/modal reachable from POS (and a
   dedicated page for admin) hitting `GET /bills` with filters — bill
   number, date, cashier, customer phone — respecting the plan's
   `saved_bill_days` window (Lite=7, Pro=90, Pro Max=unlimited) shown as an
   upgrade prompt if the user searches beyond their window.
7. **Printing**:
   - Implement `utils/escpos.ts` — builds ESC/POS byte sequences for
     thermal receipts (logo, company header from `company_settings`, line
     items, tax breakdown, footer) at configurable paper widths (58mm/80mm
     from the printer profile).
   - Implement `utils/dotmatrix.ts` — plain fixed-width text layout
     (character-grid based, no ESC/POS graphics) for dot-matrix continuous
     stationery, also configurable width.
   - Print dispatch logic picks WebUSB/WebSerial when available and the
     profile says `thermal`, otherwise sends the built payload to the Local
     Print Agent endpoint (`http://localhost:<port>/print`) documented in
     `docs/ARCHITECTURE.md`; build a minimal reference Local Print Agent as
     a small standalone Python script in `scripts/local_print_agent.py`
     (Flask/FastAPI micro-server, prints via `pywin32`/raw port on Windows)
     since the target retail PCs are Windows.
8. **Tests**: totals calculation (multiple tax slabs + discounts +
   round-off edge cases), hold/resume flow, plan-based saved-bill window
   enforcement, barcode-vs-manual-typing detection.

## Definition of Done
- [ ] A full sale can be completed via barcode scan only, keyboard only, and touch/mouse only
- [ ] Every keyboard shortcut has a visible on-screen equivalent
- [ ] Server-recomputed total always matches what's displayed pre-submit (or the UI corrects and shows why)
- [ ] Thermal (80mm) and dot-matrix print previews both render correctly with company logo/header
- [ ] Hold/resume works across a browser refresh (state not lost)
- [ ] Saved bill search respects plan window and shows a clear upgrade CTA when exceeded
- [ ] POS screen usable at 1024×768 tablet resolution without horizontal scroll
