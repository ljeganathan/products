# Manual Testing Guide

A phase-by-phase checklist for testing KOTMate TN by hand in a browser, backed by a
reusable seed script so you're never testing against an empty database.

## 1. Setup

**Start both dev servers** (from the repo root):

```
cd backend  && python -m uvicorn app.main:app --port 8000 --reload
cd frontend && npm run dev
```

**Seed demo data** (from `backend/`, with the servers running or stopped — it talks
directly to Postgres, not the API):

```
python -m scripts.seed_demo_data
```

This creates **one hotel per subscription tier** and is safe to re-run any time — it
tops up rather than duplicates (matched by company name / item code / table number /
login handle), and resets every seeded login's password to `Demo@12345` on every run.
Re-run it at the start of each testing session to guarantee fresh "today" bills for
the Reports/Dashboard checks in §13.

Full output is a credentials dump; the essentials are in §2 below. If you need a
**Product Owner** login (Phase 03) and don't already have one, create it once via:

```
! python -m scripts.create_superuser
```

(interactive — prompts for User ID/password; the seed script deliberately doesn't
touch platform-admin accounts, since that's `create_superuser.py`'s job.)

## 2. Login Reference

**URL (every role):** `http://localhost:5173/login` — a single **User ID** field
(never email) + Password.

| Tenant | Role | User ID | Password |
|---|---|---|---|
| Lite Demo Hotel | Tenant Admin | `LDH-admin` | `Demo@12345` |
| Lite Demo Hotel | Cashier | `LDH-cashier01` | `Demo@12345` |
| Lite Demo Hotel | Waiter | `LDH-waiter01` | `Demo@12345` |
| Pro Demo Hotel | Tenant Admin | `PDH-admin` | `Demo@12345` |
| Pro Demo Hotel | Cashier | `PDH-cashier01` | `Demo@12345` |
| Pro Demo Hotel | Waiter | `PDH-waiter01` | `Demo@12345` |
| Pro Max Demo Hotel | Tenant Admin | `PMDH-admin` | `Demo@12345` |
| Pro Max Demo Hotel | Cashier | `PMDH-cashier01` | `Demo@12345` |
| Pro Max Demo Hotel | Waiter | `PMDH-waiter01` | `Demo@12345` |
| Platform | Product Owner | *(whatever you chose in §1's `create_superuser` step)* | *(as chosen)* |

Every login's password is reset to `Demo@12345` on every `seed_demo_data` run, even if
you change it by hand while testing — re-run the script to get back in if you forget.

## 3. Seeded Data Reference

| | **Lite Demo Hotel** | **Pro Demo Hotel** | **Pro Max Demo Hotel** |
|---|---|---|---|
| Tenant code | `LDH` | `PDH` | `PMDH` |
| Locations | 1 (Main) | 1 (Main) | 2 (Main + Branch Two) |
| Item images | ❌ none | ✅ all 5 items | ✅ all 5 items |
| KOT printer | ❌ not registered | ✅ registered | ✅ registered (both locations) |
| Bill printer | ✅ registered | ✅ registered | ✅ registered (both locations) |

Every tenant also has, at its Main location:
- **Category**: Mains
- **5 items**: Meals (#101, ₹150), Filter Coffee (#102, ₹30), Chicken Biryani (#103,
  ₹220), Masala Dosa (#104, ₹90), Gulab Jamun (#105, ₹60) — English + Tamil names
- **Tax rule**: "Standard GST", CGST 2.5% + SGST 2.5%, default
- **Discount rule**: "Festival Offer", flat 10% (all tiers). Pro Max also has a
  **coupon**: code `WELCOME10`, 10% off
- **2 tables**: T1, T2 (AC section)
- **Waiter**: Ravi Kumar (W1), 2% incentive, linked to the `waiter01` login
- **Cashier**: Meena Devi, 1% incentive
- **4-5 finalized bills for today** (mixed payment methods, one with a discount, one
  backdated to yesterday) so Reports/Dashboard have real numbers to check
- **Hotel Master**: logo, GSTIN `33ABCDE1234F1Z5`, UPI id, Tamil-on-print enabled

---

## 4. Phase 02 — Auth & RBAC

- [ ] Log in as `LDH-admin` / `Demo@12345` → lands on `/dashboard`.
- [ ] Log in as `LDH-cashier01` → lands on `/pos`, full Hold/KOT/Bill controls visible.
- [ ] Log in as `LDH-waiter01` → lands on `/pos`, **no Bill button anywhere** (only
  Hold + Add to KOT).
- [ ] Wrong password → clear error, no crash.
- [ ] Try navigating a waiter session directly to `/reports`, `/dashboard`,
  `/admin/users` by URL → redirected away, not rendered.
- [ ] Leave a tab open past the access-token lifetime (or just wait) and perform an
  action → silently refreshes and succeeds (no forced re-login).

## 5. Phase 03 — Product Owner

*(requires a `product_owner` login — see §1 and §2)*

- [ ] Log in as product owner → lands on `/platform`.
- [ ] Tenants list shows Lite/Pro/Pro Max Demo Hotel with correct plan badges.
- [ ] Open a tenant detail page → company address, active user/location counts, plan.
- [ ] Create a brand-new tenant via the UI form → new tenant appears in the list,
  composed admin login shown (`{tenant_code}-{handle}`).
- [ ] Plans page → edit a feature flag, confirm it persists.
- [ ] Platform maintenance page loads without error.

## 6. Phase 04 — User Management

*(as `PDH-admin`, so the seat-cap headroom is visible — Pro allows 6)*

- [ ] `/admin/users` lists admin/cashier/waiter with role badges, cashier shows 1%
  incentive.
- [ ] Add a new Cashier → local handle only (not email), composed login id shown as
  read-only preview.
- [ ] As `LDH-admin` (Lite, cap = 2, already has admin + cashier = 2), try adding a
  3rd billable user → blocked with a clear upgrade message.
- [ ] Deactivate a user → confirmation dialog mentions history is preserved, not
  deleted; deactivated user can no longer log in.
- [ ] Reset a user's password as admin → they can log in with the new one.

## 7. Phase 05 — Item & Category Master

- [ ] `/admin/categories` — add/reorder/deactivate a category.
- [ ] `/admin/items` as `LDH-admin` (Lite) — **no image upload control visible**, no
  section-price override option.
- [ ] `/admin/items` as `PDH-admin` or `PMDH-admin` — image upload control present;
  open an existing seeded item (e.g. Meals #101) and confirm its placeholder image
  displays.
- [ ] Upload a new image on an item → thumbnail updates immediately.
- [ ] Item search (`/pos` search box) is typo-tolerant — try `"filtr coffee"` and
  confirm Filter Coffee still surfaces.
- [ ] Item-code quick entry on POS — type `101` + Enter → adds Meals to cart.
- [ ] Toggle `track_inventory` on an item, set a low `available_qty` (≤5) → POS grid
  shows a low-stock badge; at 0, the card greys out and stops accepting taps.

## 8. Phase 06 — Waiter Master

- [ ] `/admin/waiters` shows Ravi Kumar (W1), 2% incentive, linked to `waiter01`.
- [ ] Add a new waiter without a linked login (app-access-free) — table master should
  still allow assigning them.
- [ ] Edit incentive rate → next bill that waiter is attributed to should reflect the
  new rate (check the incentive line on the bill summary).

## 9. Phase 07 — POS Core

*(as `PMDH-cashier01`, desktop width)*

- [ ] 3-pane layout: category rail, item grid, cart. F1 = Top Selling, F2+ cycle
  categories.
- [ ] Add Meals + Filter Coffee to cart → running totals update, table number is the
  dominant visual element once a table is picked.
- [ ] Pick table T1, AC section shown as a small badge next to it, not the reverse.
- [ ] Hold a bill (Ctrl+H) → cart clears; Recall panel shows it; recall restores the
  exact cart.
- [ ] Switch table to a different section mid-cart → confirmation prompt showing
  old/new totals before applying (only if section-priced items are affected).
- [ ] Resize to tablet width → category rail moves to a horizontal top strip, cart
  stays side-by-side (not a bottom sheet).
- [ ] Resize to phone width, log in as `PMDH-waiter01` → single-column, bottom-sheet
  cart via FAB, **only Hold + Add to KOT**, no Bill button at any width for this role.

## 10. Phase 08 — KOT & Printing

- [ ] As `LDH-cashier01` (Lite — no KOT printer registered, and Lite doesn't get
  physical printing anyway), send an order to KOT → response says sent, `printed:
  false`.
- [ ] As `PDH-cashier01` or `PMDH-cashier01` (KOT printer registered) → `printed: true`.
- [ ] Open `/kot` as the tenant admin → ticket appears in New/Preparing/Ready columns
  with table+section header.
- [ ] Log in as a `kitchen`-role user if you have one (not seeded by default) → lands
  only on `/kot`, no other nav.
- [ ] Advance a ticket's status from `/kot` → updates live in a second tab open on
  `/pos`'s "KOT Tickets" popup, no manual refresh.
- [ ] Add a 2nd round of items to an already-sent order, send KOT again → only the
  new items appear on the new ticket (repeat-KOT).
- [ ] `/admin/printers` — add/edit/deactivate a printer for either target.

## 11. Phase 09 — Billing, Tax & Discount

*(as `PMDH-cashier01`, table T1)*

- [ ] Add 2x Meals to cart, click Bill → preview shows Subtotal ₹300, CGST ₹7.50, SGST
  ₹7.50, Round Off, Grand Total — **CGST and SGST always on separate lines**.
- [ ] Choose discount type "Flat %" and type `10` → discount line appears, tax
  recalculates off the discounted base. (The seeded "Festival Offer" rule in
  `/admin/discount-rules` is a reference row for that admin page, not a picker in the
  billing flow — flat % is always typed directly.)
- [ ] Apply coupon `WELCOME10` (Pro Max only) → same 10% effect via coupon path;
  try it on `PDH-cashier01` (Pro, no coupon feature) → rejected.
- [ ] Split payment across UPI + Cash that doesn't sum to the grand total → blocked
  from finalizing until it matches exactly.
- [ ] Finalize a bill → printed confirmation (bill printer is registered on all seed
  tenants), reprint button available afterward.
- [ ] `/billing/history` — search by bill number / date / table / waiter, reprint an
  old bill and confirm the figures are identical to the original.
- [ ] As `LDH-waiter01` or `PDH-waiter01`, confirm there is **no Bill button and no
  payment UI anywhere**, on any device width.
- [ ] `/admin/tax-rules` and `/admin/discount-rules` — CRUD, deactivate/reactivate.

## 12. Phase 10 — Settings & Hotel Master

*(as `PMDH-admin`, which has 2 locations)*

- [ ] `/admin/settings` → General tab shows a location switcher (only appears because
  Pro Max has 2 locations); switch to Branch Two and confirm the form reloads with
  that location's own Hotel Master.
- [ ] Edit GSTIN to one starting `27` (Maharashtra) while State is still Tamil Nadu →
  non-blocking warning banner appears, save still succeeds.
- [ ] Toggle "Show Tamil item names on printed KOT tickets and bills" off, send a KOT
  and finalize a bill → printed output (check backend logs) omits Tamil; the **POS
  screen grid still shows both languages** regardless.
- [ ] Upload a new logo → print-preview thumbnail on the same page updates instantly.
- [ ] Locations tab — as `LDH-admin` (Lite, cap 1, already at 1) → "+ Add Location" is
  disabled with an upgrade note. As `PMDH-admin` (cap 5, at 2) → can add up to 3 more.
- [ ] Printers/Tax/Categories tabs correctly link out to their existing dedicated
  admin pages.

## 13. Phase 11 — Reports & Dashboard

*(re-run `python -m scripts.seed_demo_data` first if it's a new day, so "today" has
bills)*

- [ ] `/dashboard` as `LDH-admin` (Lite) → KPI cards only (Today's Sales, Bill Count,
  Average Bill Value, Top Item), explicit "Charts... available on Pro/Pro Max" note,
  **no chart, no multi-location section**.
- [ ] `/dashboard` as `PDH-admin` (Pro) → same KPI cards **plus** an hourly sales bar
  chart; still no multi-location section.
- [ ] `/dashboard` as `PMDH-admin` (Pro Max) → KPI cards + chart + a **Multi-Location
  Comparison** table showing both Main and Branch Two with independent bill
  counts/sales.
- [ ] `/reports` as `LDH-admin` → all 9 report tabs work, but **no export buttons at
  all**.
- [ ] `/reports` as `PDH-admin` → **CSV export only** (no PDF/Excel buttons).
- [ ] `/reports` as `PMDH-admin` → CSV + PDF + Excel all present; download one of
  each and open it — figures should match the on-screen table exactly.
- [ ] Sales Summary for today: cross-check Bill Count / Grand Total against what
  `/billing/history` shows for the same date range — must match exactly.
- [ ] Waiter Incentive and Cashier Incentive reports both show Ravi Kumar / Meena
  Devi's figures independently — the same underlying bill's net sale value should
  appear in *both* reports without being summed into one merged total anywhere.
- [ ] Not pre-seeded — if you want to check it: add a waiter/cashier with incentive
  rate `0`, bill one order through them, then confirm they do **not** appear as a
  ₹0.00 row in the incentive report (a 0%-rate line should be omitted entirely, not
  just zeroed out).
- [ ] Z-Report for today reconciles bill-for-bill against Sales Summary, with a
  payment-method breakdown that sums to the grand total.
- [ ] As `PMDH-waiter01`, confirm `/reports` and `/dashboard` are both entirely
  unreachable (redirected away), not just missing a nav link.

---

## Troubleshooting

- **Seed script fails with a 403 "plan limit reached"**: you've already run it enough
  times to hit Pro Max's 5-location cap via other manual testing — check
  `/admin/settings` → Locations on `PMDH-admin` and deactivate anything you added by
  hand before re-running.
- **Bills stop appearing as "today" data**: the seed script only tops up when a
  location has fewer than 4 bills *for the current calendar day* — re-run it after
  midnight to get a fresh batch.
- **Item images look identical across items**: they're intentionally simple generated
  placeholders (colored rectangle + item name), not real photos — that's expected for
  seed data, not a bug.
