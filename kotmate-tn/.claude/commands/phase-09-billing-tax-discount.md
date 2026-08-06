# /phase-09-billing-tax-discount

Read `CLAUDE.md` §6, §8, §9, §10 before starting.

## Goal
Finalize billing: configurable tax (Tamil Nadu GST/CGST+SGST — always shown as two separate lines, never merged), discounts, round-off to the nearest ₹1, multi-payment split (UPI-first per §9), QR code (UPI) on bill, bill printing (thermal/dot-matrix), and audit logging of price overrides/discounts.

## Scope
1. **Backend**
   - `tax_rules`: configurable rate(s) (e.g. CGST 2.5% + SGST 2.5%), applied at bill or item level per plan tier (Lite = single flat rate; Pro/Pro Max = multi-rate / per-item override per CLAUDE.md §6). CGST and SGST are always distinct rate rows — never collapse into one combined "GST" rate, since both must render as separate lines on screen and print (CLAUDE.md §9).
   - `discount_rules`: flat % (all tiers), item-level (Pro+), coupon-code rules (Pro Max) — service layer computes final bill totals; write unit tests for tax+discount math (rounding rules matter for statutory compliance).
   - `POST /api/v1/bills` — converts an `open`/`held` order into a finalized bill: computes subtotal from each `order_items.unit_price` (already snapshotted at the section-resolved price when added in Phase 07 — billing does not re-resolve section prices, it trusts the snapshot), CGST breakup, SGST breakup, discount, **`round_off_amount`** (signed delta rounding the post-tax total to the nearest ₹1), grand total; supports split payment array (`[{method: upi, amount}, {method: cash, amount}, {method: card, amount}]`) summing to grand total. `require_role("tenant_admin", "pos_user")` — a `waiter` token is rejected with 403 even if called directly, not just hidden in the UI (CLAUDE.md §5/§9). Once committed, the order flips to `billed`, which is what drops it out of Phase 07's "KOT Tickets" popup and Phase 08's Kitchen Display — no separate ticket-side "billed" flag to maintain.
   - Bill print render (reuses Phase 08 printer adapters) with hotel logo, GSTIN, QR code (UPI deep link, `upi://pay?pa=...&am=...`) generated server-side as an image for thermal printers. Header includes table number + section (e.g. "Table: T5 (AC)"), or the section name alone for Takeaway/Online Delivery — same convention as the KOT ticket (Phase 08). Amounts printed with Indian digit grouping (₹1,25,000 style — CLAUDE.md §9); CGST/SGST and "Round Off" always print as their own lines, even when Round Off is ₹0.00.
   - `audit_log` entries for any manual price override or discount applied above a configurable threshold.
2. **Frontend**
   - Bill summary panel in POS: separate CGST and SGST line items (never merged), discount entry (validated against tenant's plan-allowed discount types), an explicit "Round Off" line, split-payment UI ordered **UPI, then Cash, then Card** with equal-weight buttons (CLAUDE.md §9) — all amounts in Indian digit grouping.
   - Print preview modal before dispatch to printer.
   - "Old bill search" (by bill number, date, table, waiter) with reprint/duplicate option.

## Acceptance Criteria
- Tax and discount math verified with unit tests against known TN restaurant billing examples (rounding to nearest paisa/rupee configurable); round-off math verified separately (e.g. ₹247.60 → ₹248.00 grand total with `round_off_amount = +0.40`).
- Split payment totals must equal grand total or the bill cannot be finalized.
- QR code renders correctly on a simulated thermal print output (image bytes validated in test, not just visually).
- CGST and SGST always render as two distinct lines on screen and print, never a single merged line, including when both rates happen to be equal.
- Old bill search returns correct results and reprint produces an identical bill.
- A `waiter`-role token calling `POST /api/v1/bills` gets 403, regardless of order/table ownership.
