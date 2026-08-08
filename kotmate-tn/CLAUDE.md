# CLAUDE.md — KOTMate TN
### Multi-Tenant Hotel / Restaurant KOT & Billing SaaS for Tamil Nadu

> This file is the single source of truth for Claude Code. Read this in full before executing any `/phase-*` command. Every phase command references sections of this file — do not duplicate architecture decisions inside phase files, only execution steps.

---

## 1. Product Summary

**KOTMate TN** is a subscription-based, multi-tenant Point-of-Sale + Kitchen Order Ticket (KOT) + Billing web application for hotels and restaurants in Tamil Nadu. It supports bilingual (English + Tamil) item names, is responsive across Desktop / Tablet / Mobile (mobile gets a simplified touch-first UI, officially supported on phones from "Pro" and "Pro Max" tier screen classes), and is sold as SaaS with three tiers: **Lite, Pro, Pro Max**.

Product Owner (Senthil) = platform super-admin who manages tenants, subscriptions, plan features, and platform maintenance. Each hotel/restaurant that signs up is a **Tenant**, with its own Admin and POS/Waiter/Kitchen users, scoped by Role-Based Access Control (RBAC).

---

## 2. Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS + shadcn/ui |
| State/Data | TanStack Query + Zustand (UI state) |
| Backend | FastAPI (Python 3.11) + Pydantic v2 |
| ORM | SQLAlchemy 2.0 (async) + Alembic migrations |
| Database | PostgreSQL 15 (Hostinger managed / VPS) |
| Auth | JWT (access + refresh), bcrypt password hashing, RBAC middleware |
| File storage | Local disk (`/uploads`) initially, abstracted behind a storage interface for later S3/Azure Blob swap |
| Printing | Browser-side ESC/POS via WebUSB/WebSerial bridge OR a lightweight local print-agent (configurable), abstracted so dot-matrix (raw text/ESC-P) and thermal (ESC/POS) both work |
| Realtime | WebSockets (FastAPI) for KOT-to-kitchen live updates, order status |
| Deployment | Hostinger VPS, Docker Compose (nginx + frontend static + backend uvicorn/gunicorn + postgres) |
| CI | GitHub Actions (lint, test, build) |

---

## 3. Repository Structure

```
kotmate-tn/
├── CLAUDE.md                     # this file
├── .claude/commands/             # phase-wise slash commands for Claude Code
│   ├── phase-00-bootstrap.md
│   ├── phase-01-database.md
│   ├── phase-02-auth-rbac.md
│   ├── phase-03-product-owner.md
│   ├── phase-04-user-management.md
│   ├── phase-05-item-category-master.md
│   ├── phase-06-waiter-master.md
│   ├── phase-07-pos-core.md
│   ├── phase-08-kot-printing.md
│   ├── phase-09-billing-tax-discount.md
│   ├── phase-10-settings-hotel-master.md
│   ├── phase-11-reports-dashboard.md
│   ├── phase-12-import-export-deploy.md
│   ├── phase-13-platform-console-ux.md
│   ├── phase-14-invoicing-dashboard-alerts.md
│   ├── phase-15-admin-nav-settings-printers.md
│   ├── phase-16-item-master-overhaul.md
│   ├── phase-17-discount-rules-bill-history.md
│   ├── phase-18-pos-core-fixes.md
│   ├── phase-19-pos-multilocation-seating.md
│   └── phase-20-dashboard-pos-polish.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/          # config, security, deps, middleware
│   │   ├── db/             # session, base, migrations (alembic/)
│   │   ├── models/         # SQLAlchemy models (one file per domain)
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── api/v1/         # routers per domain
│   │   ├── services/       # business logic (billing calc, tax, kot routing)
│   │   ├── ws/              # websocket managers (kitchen display)
│   │   ├── printing/        # printer adapters (thermal_escpos.py, dotmatrix.py)
│   │   └── utils/
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/             # routes, layout shells (desktop/tablet/mobile)
│   │   ├── modules/
│   │   │   ├── auth/
│   │   │   ├── product-owner/     # tenant + subscription + platform maintenance
│   │   │   ├── admin/              # user management, settings
│   │   │   ├── items/              # item + category master
│   │   │   ├── waiters/
│   │   │   ├── pos/                 # main billing screen
│   │   │   ├── kot/
│   │   │   ├── reports/
│   │   │   └── dashboard/
│   │   ├── components/ui/    # shadcn primitives + shared components
│   │   ├── hooks/
│   │   ├── lib/               # api client, i18n, printer bridge
│   │   ├── locales/           # en.json, ta.json
│   │   └── styles/
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── subscription-tiers.md
│   ├── eta-roadmap.md
│   ├── db-schema.md
│   └── api-contract.md
├── docker-compose.yml
└── .gitignore
```

---

## 4. Multi-Tenancy Model

- **Single database, shared schema, `tenant_id` on every tenant-scoped table** (row-level isolation via SQLAlchemy query filters + Postgres RLS policies as defense-in-depth).
- `tenants` table = one row per subscribing **Company** account (the "Company Master": company name + address, managed by `tenant_admin`), plus a short platform-assigned **`tenant_code`** (2-10 chars, e.g. `HTL1`) used only to compose login ids (see §5) — never shown to customers, not part of billing/branding.
- `tenant_locations` table = one row per **hotel location** owned by that company (own name/address, own `hotel_master` data — logo/GSTIN/UPI, printers, tax config, seating sections, tables) but shared subscription billing and a shared user pool. **Every tier now supports multiple locations**, capped by `plans.max_locations`: **Lite = 1, Pro = up to 2, Pro Max = up to 5**. The Company Master screen (Phase 10) is where `tenant_admin` adds locations up to that cap; adding one more prompts an upgrade if the cap is reached.
- Product Owner operates in a separate `platform_admin` scope, outside any tenant, with cross-tenant visibility.

---

## 5. Roles (RBAC)

**Login identity:** every login — including Product Owner — is by **`user_id`** (a short, admin-assigned username), **never email**, and the login form is always a single User ID field (no separate company/tenant selector). `user_id` is **globally unique across the whole platform** (one unique constraint, no per-tenant scoping) so a single field can always resolve unambiguously to one account: for tenant-scoped roles it's auto-composed at creation as `{tenant.tenant_code}{local_handle}` — **concatenated with no separator** (e.g. `HTL1CASHIER01`) — from a local handle the `tenant_admin` picks in User Management (Phase 04) — the admin only has to avoid colliding with *their own* staff, not every other tenant's, since the `tenant_code` prefix makes cross-tenant collisions structurally impossible. `product_owner` accounts have no tenant and use a bare, unprefixed `user_id`. There is no email-based self-service password reset in v1; resets are admin-triggered — for tenant-scoped staff by their own `tenant_admin` (Phase 04), for a tenant's admin account itself by `product_owner` (Phase 13, `POST /platform/tenants/{id}/reset-admin-password`). *(Accounts created before this format changed keep their original hyphenated `{tenant_code}-{local_handle}` id — not renamed retroactively.)*

| Role | Scope | Key Permissions |
|---|---|---|
| `product_owner` | Platform | Manage tenants, subscriptions/plans, platform maintenance, view all-tenant analytics, feature flags |
| `tenant_admin` | Tenant | User management (add/edit/deactivate cashiers, waiters & KOT users within plan limits), Company Master (hotel locations, up to plan cap), settings, item/category master, seating sections & table master, sets waiter/cashier incentive rates, reports, all POS functions |
| `pos_user` (cashier) | Tenant/Location | POS billing, add items to KOT, hold/recall bill, pick up any open KOT ticket by ticket no/table for billing (§11), print; bills they ring up are auto-attributed to themself for cashier incentive tracking |
| `waiter` | Tenant/Location | Table assignment/order capture, add items to KOT — **cannot finalize/print a bill or take payment**, on mobile or otherwise; billing is `pos_user`/`tenant_admin`-only, enforced at the API layer, not just hidden in the UI (§9, Phase 09). Orders they create are auto-attributed to themself for incentive tracking |
| `kitchen` (**"KOT User"** in all UI copy — role code stays `kitchen` for backend/API continuity with Phase 01-02) | Tenant/Location | KOT ticket list only, organized by ticket number (read-only order queue, mark "preparing"/"ready"); no POS, billing, reports, or any other screen — a KOT user's login lands only on `/kot` |

Number of `tenant_admin`/`pos_user` seats addable is capped per subscription tier (see §6). Enforced server-side in the user-management service, not just UI. Waiter and cashier **incentive rates** (%, applied to net sale value — post-discount, pre-tax) are set per-user by `tenant_admin`: in User Management (Phase 04) for cashiers, in Waiter Master (Phase 06) for waiters — see §11.

---

## 6. Subscription Tiers & Feature Matrix

| Feature | Lite | Pro | Pro Max |
|---|---|---|---|
| POS billing + KOT (screen-only) | ✅ | ✅ | ✅ |
| Users (Admin + POS) | up to 2 | up to 6 | Unlimited |
| Hotel locations (Company Master) | 1 | up to 2 | up to 5 |
| Item master with Tamil name | ✅ | ✅ | ✅ |
| Item image upload | ❌ | ✅ | ✅ |
| Category master | ✅ | ✅ | ✅ |
| Waiter master | ✅ | ✅ | ✅ |
| Seating sections & table tagging (AC/Non-AC/Rooftop/etc.) | ✅ | ✅ | ✅ |
| Per-section item price override | ❌ (flat price only) | ✅ | ✅ |
| Waiter & cashier incentive tracking | ✅ | ✅ | ✅ |
| Top-selling item quick buttons (image) | text-only | ✅ image | ✅ image |
| KOT printer output (physical) | ❌ (screen KOT only) | ✅ | ✅ |
| Bill printer (thermal/dot-matrix) | ✅ basic | ✅ | ✅ |
| Hold / recall bill | ✅ | ✅ | ✅ |
| Tax configuration (GST/CGST/SGST) | basic single rate | multi-rate | multi-rate + per-item override |
| Discounts | flat % only | flat + item-level | flat + item-level + coupon rules |
| QR code on bill (UPI) | ❌ | ✅ | ✅ |
| Hotel master + logo on print | ✅ | ✅ | ✅ |
| Reports (sales, item, category, waiter, cashier, waiter/cashier incentive, tax) | basic (view only) | ✅ + export CSV | ✅ + export CSV/PDF/Excel |
| Dashboard analytics | basic KPIs | + charts | + multi-location comparison |
| Item import/export | ❌ | ✅ export | ✅ import + export |
| Kitchen display (KDS) live view | ❌ | ✅ | ✅ |
| Priority support | ❌ | ❌ | ✅ |

---

## 7. Subscription Pricing (INR, per month, flat per company account)

| Tier | Price/month | Price/year (2 months free) | Locations included | Target |
|---|---|---|---|---|
| **Lite** | ₹999 | ₹9,990 | 1 | Small tea shops / single-counter eateries |
| **Pro** | ₹2,499 | ₹24,990 | up to 2 | Mid-size restaurants, KOT printing needed |
| **Pro Max** | ₹4,999 | ₹49,990 | up to 5 | Multi-branch hotels/restaurant chains |

Add-ons (all tiers unless noted): extra POS-user seat beyond cap ₹199/user/month · extra hotel location beyond plan cap (Pro/Pro Max only) ₹999/location/month · SMS/WhatsApp bill notifications ₹0.35/msg (future phase) · onboarding/data-migration one-time fee ₹2,999.

*(These are suggested anchor prices for the TN small-hotel/restaurant market — validate against 2-3 local competitor POS vendors before final pricing.)*

---

## 8. Core Domain Entities (high level — full DDL in `docs/db-schema.md`, built in Phase 01)

`tenants` (company name, `email`, `phone`, Indian-format address — the Company Master, plus `tenant_code`, a short platform-assigned prefix used to compose tenant-scoped login ids — see §5), `tenant_locations` (per-hotel name + Indian-format address, capped by plan — see §6/§7), `subscriptions`, `invoices` (tenant subscription billing — `amount`, `status` draft/sent/paid/overdue, `due_date`, `paid_date`, distinct from POS `bills` — Phase 14), `plans` (incl. `max_users`, `max_locations`), `users` (`user_id` globally-unique login handle, composed as `{tenant_code}{local_handle}` for tenant roles, no separator — never email, role, `incentive_rate` for `pos_user`/cashier), `roles`, `categories` (name_en, name_ta, `icon_url` — nullable, POS falls back to a generic icon when unset, not plan-gated, Phase 18 — display_order, is_active), `items` (name_en, name_ta, image_url, price, tax_class, `track_inventory`, `available_qty` — soft stock count, both nullable/off by default, see §11, is_active), `seating_sections` (name_en, name_ta, `is_seating`, display_order, is_active), `item_section_prices` (item_id, section_id, price — per-item override, falls back to `items.price` when absent), `waiters` (waiter_number, name, phone, incentive_rate, is_active), `tables` (table_number, location_id, `section_id`, seating_capacity — `status` free/occupied is computed on read from live `orders`, not a stored column, so it can never drift out of sync — Phase 19), `orders` (incl. `waiter_id`, `pos_user_id`, `table_id`, `party_label` — nullable, distinguishes concurrent parties/bills at the same table, see §11 seat splitting), `order_items`, `kot_tickets`, `bills` (incl. `round_off_amount`), `bill_items`, `payments`, `tax_rules` (CGST/SGST tracked as distinct rates, never merged), `discount_rules`, `printers`, `hotel_master` (per-location: logo, Indian-format address — door_no/street/city/district/state/pincode — GSTIN, QR/UPI id), `audit_log`.

Indian-format address = `door_no`, `street`, `city`, `district`, `state` (Indian states/UTs enum), `pincode` (6-digit) — not a single free-text "address" field.

---

## 9. UI / Responsiveness Rules

Design point of view: the primary user is a **counter cashier or waiter in a Tamil Nadu hotel/restaurant** — often coming from a background of Tally, Marg, or DOS-era billing machines, sometimes mixed-literacy in English/Tamil, working long single-session shifts on the same device. Optimize for speed and familiarity over Western SaaS minimalism.

### Design language (applies at every breakpoint)
- **Dense, colorful, not minimalist.** This audience reads whitespace-heavy, muted-gray SaaS layouts as "empty/unfinished," not "clean." Keep saturated category/item color blocks (turmeric gold, banana-leaf green, chili red) and a denser grid (more items per screen, smaller card padding) than a typical Western POS — large TN meals hotels routinely run 100–300+ item menus and staff resent extra scrolling.
- **Indian number formatting.** ₹ prefixed with no space, lakh/crore digit grouping (₹1,25,000, not ₹125,000); show paise only when non-zero (₹120, not ₹120.00; but ₹120.50 in full) — matches how local printed bills already look.
- **Table number is the dominant visual anchor, everywhere** (cart header, KOT ticket, printed bill) — larger and bolder than item names or even the total, because floor operations run on staff calling out table numbers out loud. The seating section/class is a smaller badge next to it, not the reverse (e.g. **"T5"** big, `AC` small badge beside it).
- **Item-code quick entry.** Many TN counters use laminated menus with numeric item codes (e.g. "301 – Meals", "205 – Filter Coffee"). Provide a small numeric code field next to search — type code + Enter adds the item and refocuses the field — faster than touch/search for repeat orders and matches muscle memory from calculator-style billing machines many operators already know.
- **Bilingual-by-default on the staff-facing grid**, not toggle-hidden: item buttons show English (primary line) + Tamil (smaller secondary line) stacked together at all times, rather than one language hiding the other — mixed-literacy staff benefit from seeing both simultaneously. `hotel_master.show_tamil_names` instead controls the **customer-facing KOT/bill print**, where space is tighter and a single restaurant may want print-Tamil off even if staff-screen Tamil is always on.
- **Meals/Thali as oversized quick-tiles.** TN "Full Meals / Half Meals / Mini Meals" ordering is single-tap-combo, not itemized à la carte — render these as larger, visually distinct tiles (pinned in Top Selling or leading their category) rather than same-size as a regular item, since they're disproportionately high-frequency.
- **UPI-first payment order.** Payment buttons list UPI before Cash/Card (UPI is now the dominant rail even in small TN towns) with a generic "UPI" badge (not a specific app logo, to avoid trademark issues), sized equal to Cash/Card — never smaller/secondary.
- **GST shown as two lines, always.** CGST and SGST are always rendered as separate line items on-screen and on print, never merged into one "GST" line — TN customers are trained to check both are present.
- **Round Off line, always shown.** Bill total rounds to the nearest ₹1 with an explicit "Round Off (+₹0.40)" line rather than silently absorbing it — an unexplained rounding difference reads as suspicious to a customer checking the bill.
- **Indian address format** everywhere an address is captured (Company/Hotel Master, Phase 10): Door No./Building, Street/Area, City, District, **State** (dropdown of Indian states/UTs, drives GST state code validation against GSTIN), 6-digit **PIN Code** — not a generic City/State/Zip layout.
- Touch targets ≥44px on touch devices; full mouse+keyboard parity on desktop.
- Theme: colorful, high-contrast, configurable accent color per tenant (branding-lite for Pro Max).
- Login screen: a single **User ID** field (not styled/validated as an email input) + password, for every role including Product Owner.
- Table selector shows the seating **section/class alongside the table number** (e.g. "T5 · AC", "T12 · Rooftop") so staff see it before adding items. Non-seating sections (Takeaway, Online Delivery) skip table selection entirely — POS shows the section itself as the selectable chip. The selected section drives which `item_section_prices` override applies (Pro+); switching a bill's table/section after items are already in the cart prompts a price-recalculation confirmation rather than silently changing totals.

### Desktop
- Full 3-pane layout: left category tabs (first always "Top Selling", last always "All" — showing every item regardless of category, Phase 18) + item grid, center/right running order-cart, keyboard shortcuts (F-keys for categories, next two F-keys cycle table/waiter, Enter to add, Ctrl+K search, Ctrl+P print/KOT, Esc clears the draft cart). This is typically the **main billing counter machine**, run for hours at a stretch — keyboard-first flow is primary, and the item-code field auto-refocuses after every add so a cashier can move through a long repeat order without touching the mouse. "Top Selling" is manually-pinned items (`items.is_top_seller`) first, backfilled with the tenant's actual best-sellers from the last 7 days when fewer than 8 are pinned (Phase 18) — not a static, owner-curated-only list.

### Tablet
- Category rail moves from the left column to a horizontal strip across the **top** — a side rail leaves too little width once the cart panel is also on screen at tablet portrait sizes. Items and the running-order cart still sit side-by-side below it, though: this is **not** the simplified mobile flow — no bottom-sheet cart, no FAB, and table/waiter selection stays visible alongside the order at all times, only touch target sizing and panel widths scale down from desktop. Table/section and waiter selectors stay one tap away without opening a modal, since a tablet is often used standing/moving (e.g. a floor supervisor billing at a guest's table) rather than seated at a fixed counter. Item-code entry is present but secondary to touch — useful when a Bluetooth numeric/barcode scanner is paired, common in TN retail, but not assumed.

### Mobile (phone)
- Simplified single-column flow — category chips in a horizontally-scrollable strip across the top (same top-strip pattern as tablet, not a side rail), items below, cart as a bottom sheet reached via a floating cart button, no overlapping panels. This is the **waiter's order-taking device on the floor** (§5), not the main billing counter, so it's optimized for one-handed use while walking between tables: the cart FAB and the bottom sheet's primary actions stay within thumb reach at the bottom of large-screen ("phablet") Android devices common in TN, rather than requiring a reach to the top. Officially tuned/tested for large-screen phones (Pro/Pro Max device class); fluid breakpoints keep it usable on smaller phones without being the primary target.
- **Billing action is role-gated, not device-gated.** For a `waiter` login the bottom sheet's only primary actions are **Hold** and **Add to KOT** — there is no Bill/print/payment button anywhere in a waiter's session, mobile or otherwise (§5), since a waiter can originate and send an order to the kitchen but never finalizes it. A `pos_user` (cashier) using the same mobile breakpoint — e.g. a counter phone — still sees the full Hold/KOT/Bill set, because the restriction follows the logged-in role, not the screen size.
- **Network-tolerant by design.** Smaller-town TN establishments often have patchy WiFi/4G at the till. Orders are server-persisted (so Hold works across devices), but the mobile UI must show an explicit "Saving…/Saved" sync indicator and queue add-item actions locally rather than blocking the waiter mid-order on a network blip.

---

## 10. Printing Architecture

- `printing/` module in backend exposes a common `PrintJob` interface; two adapters: `escpos_thermal.py` (thermal, image logo, QR) and `dotmatrix_raw.py` (plain ESC/P text layout, no images).
- Printer registered in Settings with type (`thermal`/`dotmatrix`), connection (`network`/`wifi`/`usb`/`bluetooth`/`local-agent` — Phase 15), paper width (58mm/80mm/241mm presets or a free-entry custom mm value, since actual hardware width varies), and target (KOT printer vs Bill printer — a tenant can have separate printers for kitchen and billing counter). Connection-specific fields (IP+port for network/wifi, paired device name for bluetooth) live in an unstructured `connection_details` JSON blob rather than dedicated columns, since each connection type needs a different shape and this only ever feeds the printing adapter, never gets queried on.
- KOT and Bill are independently templated (`templates/kot.txt.jinja`, `templates/bill.txt.jinja` and an HTML/ESC-POS binary variant).
- Both templates print the table's seating **section/class next to the table number** (e.g. "Table: T5 (AC)") so kitchen and customer copies both reflect it; Takeaway/Online Delivery orders print the section name in place of a table number.

---

## 11. Trend Features Included (beyond the base ask)

- Real-time KDS (Kitchen Display System) websocket queue as a screen alternative/companion to physical KOT printing — cards organized primarily by **ticket number** (table/section shown alongside, same visual convention as the printed ticket, §10), columns New/Preparing/Ready. Visible only to the `kitchen` ("KOT User") role, whose login has no other screen (§5).
- **KOT-to-billing handoff** — a waiter (mobile) and the cashier (counter) are frequently two different logged-in users, so the billing screen carries a small **"KOT Tickets"** button that pops up every currently open (not yet billed) ticket across the location, listed by ticket number + table/section. Selecting one loads that order into the billing screen for finalization. No new status field is needed to "clear" a ticket from this list: it's a live filter on the parent order's status (`open`/`held` = shown, `billed` = gone), so the same query also naturally drops the ticket once Phase 09 finalizes the bill.
- Table management with visual floor-plan/table-status view (free/occupied — computed live from open orders, see §8, not a separate "billed" transient state).
- **Seat/party splitting** — a table can hold more than one concurrent, independent bill via a nullable `orders.party_label` string (e.g. "Party 1"/"Party 2"). Tapping an occupied table in the POS table picker (Phase 07/19) offers "resume Party N" (loads that party's existing cart) or "+ New Party" (starts a fresh order at the same table, its own tab/bill) rather than only ever repurposing whatever draft was already in memory. A Postgres partial unique index (`tenant_id`, `table_id`, `party_label` WHERE `status='open'`) stops two open parties at the same table from colliding on the same label; the table only reads as "free" again once every party at it has billed out (Phase 19, POS-22/POS-25).
- **Multi-location POS/Dashboard** — a tenant with more than one location gets a location picker in the POS header (persisted so a fixed counter machine doesn't need re-picking every reload) and on the tenant Dashboard; tables, waiters, and open orders are all scoped to whichever location is currently selected. Dashboard KPI cards accept the same location filter, independent of the Pro Max-only Multi-Location Comparison table (§6) which already spans every location for a date range (Phase 19, POS-35).
- UPI QR code auto-generated per bill amount.
- **Low-stock/86'd item awareness** (soft inventory, not a full inventory module — opt-in per item via `items.track_inventory`, with `items.available_qty` as the running count; items that don't opt in behave exactly as before, no count shown anywhere). `available_qty` decrements when a KOT ticket actually fires for that item (Phase 08) — not at cart-add time, since a waiter/cashier is still free to remove an item before sending it to the kitchen; it's the KOT send that commits the item as "being prepared." Two surfaces read the same count: **(1)** the KOT/Kitchen Display (Phase 08) shows a low-stock banner/badge for any tracked item once its `available_qty` drops to **≤5**, so kitchen staff can flag a physical shortage before it becomes a walked-back promise at the table; **(2)** the POS item grid (Phase 07) shows the same "only N left" badge directly on that item's own card — not a separate popup — and once `available_qty` hits **0** the card greys out and stops accepting taps/clicks/item-code entry entirely, on every device class. Both surfaces stay live via the same location-scoped websocket Phase 08 already opens for KOT tickets (typed messages: `kot_ticket` vs `item_stock`), so a stock change from one cashier's KOT send is reflected on every other open POS/KOT screen at that location within the same session, not just on next reload. `tenant_admin`/Item Master (Phase 05) is where `track_inventory` is toggled and `available_qty` is set/restocked (e.g. at the start of a shift) — there's no automatic restock or end-of-day reset, since this is deliberately a soft running count, not a real inventory ledger. **(3)** The tenant Dashboard's **Low Stock Items** widget (Phase 20, replacing the old "Top Item" KPI box) lists every tracked item currently at or under the same ≤5 threshold, tenant-wide (not location-scoped, since stock isn't tracked per-location) — a plain polling query on page load rather than the live websocket the other two surfaces use, since a dashboard glance doesn't need same-session push updates.
- Daily Z-report / shift closing summary.
- Multi-payment split (cash + UPI + card) per bill.
- Audit log for price overrides & discounts (loss-prevention).
- Staff incentive tracking — configurable per-staff incentive % for both **waiters** and **cashiers** (`pos_user`), set by `tenant_admin` in Waiter Master (Phase 06) and User Management (Phase 04) respectively, computed on net sale value (post-discount, pre-tax) per bill and stored on `bills.waiter_incentive_amount`/`cashier_incentive_amount`. Purely a backend/reporting concern (Phase 18, POS-27) — not shown on the POS screen at all (removed from the on-screen cart summary, on top of already never having been on the customer print) and surfaced only via Phase 11's reports. A `waiter` login auto-attributes the order to themself; a `pos_user` login is always the cashier-of-record for bills they ring up; `tenant_admin`/`pos_user` can assign any waiter to a table. Rolled up in Phase 11 as four distinct reports — waiter-wise sales, cashier-wise sales, waiter incentive (payout worksheet), and cashier incentive (payout worksheet).
- Seating-section-aware pricing — a **Seating Sections master** (e.g. AC, Non-AC, Rooftop, Family, Takeaway, Online Delivery) tags every table (`tables.section_id`). Item price can be overridden per section via `item_section_prices` (item_id, section_id, price) instead of a blanket markup, so an owner can raise mains for AC seating while keeping drinks/desserts flat — falls back to the item's base price when no override exists (Pro+; Lite uses a single flat price but sections are still available for table organization/reporting).

---

## 12. Execution Order for Claude Code

Run each phase as its own Claude Code session/command, in order, only starting phase N+1 after phase N is verified working (backend boots, migrations apply, frontend builds, feature manually testable):

```
/phase-00-bootstrap
/phase-01-database
/phase-02-auth-rbac
/phase-03-product-owner
/phase-04-user-management
/phase-05-item-category-master
/phase-06-waiter-master
/phase-07-pos-core
/phase-08-kot-printing
/phase-09-billing-tax-discount
/phase-10-settings-hotel-master
/phase-11-reports-dashboard
/phase-12-import-export-deploy
```

Phases 00-12 are the original build. `/phase-13` onward is a second wave fixing issues found in manual testing of that build (see each command file's own goal/scope/acceptance criteria):

```
/phase-13-platform-console-ux
/phase-14-invoicing-dashboard-alerts
/phase-15-admin-nav-settings-printers
/phase-16-item-master-overhaul
/phase-17-discount-rules-bill-history
/phase-18-pos-core-fixes
/phase-19-pos-multilocation-seating
/phase-20-dashboard-pos-polish
```

Each command file is self-contained: goal, scope, files to create/modify, acceptance criteria. See `docs/eta-roadmap.md` for time estimates per phase.
