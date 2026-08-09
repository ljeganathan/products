# KOTMate TN — Database Schema

Built in Phase 01. See `CLAUDE.md` §4 (multi-tenancy model) and §8 (entity list) for the
product-level rationale — this doc is the implementation-level ERD.

## Conventions

- **UUID primary keys** on every table (`id`, `Uuid`/`gen_random`-free — Python-side
  `uuid.uuid4()` default via SQLAlchemy). Defense-in-depth on top of RLS: a leaked or
  guessed ID from one tenant can't be walked sequentially into another tenant's rows.
  Human-facing sequence numbers (bill number, KOT ticket number, waiter number, table
  number, item code) are separate text fields, not the PK.
- **`tenant_id`** — every tenant-scoped table carries a `tenant_id` FK to `tenants.id`
  (NOT NULL, `ON DELETE CASCADE`), plus a composite `(tenant_id, id)` index. `tenants`,
  `plans`, and `roles` are the only tables without it (platform-level, shared).
  `users.tenant_id` is the one exception that's nullable — `NULL` means `product_owner`.
- **Soft delete** — `is_active` boolean, not hard deletes, on every master-data table
  (`users`, `tenant_locations`, `waiters`, `tables`, `items`, `categories`,
  `seating_sections`, `printers`, `discount_rules`, `tax_rules`, `plans`). Preserves
  historical order/bill/audit attribution (CLAUDE.md §5 phase-04 rationale).
- **Timestamps** — `created_at`/`updated_at` (`timestamptz`, server-side `now()`) via a
  shared mixin on every table.
- **Enums as CHECK constraints, not native Postgres ENUM types** — a plain `String` +
  `CHECK ... IN (...)` (backed by Python constants in `app/core/constants.py`) instead of
  `CREATE TYPE ... AS ENUM`. Adding/renaming a value later is a normal migration instead
  of the `ALTER TYPE` dance — relevant for `INDIAN_STATES` especially, since Indian
  state/UT boundaries have changed within living memory (e.g. J&K/Ladakh in 2019).
- **Naming convention** — Alembic autogenerate uses a fixed naming convention
  (`app/db/base.py`) so constraint/index names are stable and predictable across runs
  rather than Postgres-assigned defaults.

## Tables

### Platform (no `tenant_id`)

**`plans`** — Lite / Pro / Pro Max (CLAUDE.md §6/§7)
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| code | varchar(20) unique | `lite` / `pro` / `pro_max` |
| name | varchar(50) | |
| max_users | int, **nullable** | NULL = unlimited (Pro Max) |
| max_locations | int NOT NULL | 1 / 2 / 5 |
| price_monthly, price_yearly | numeric(10,2) | |
| features | jsonb | rest of the §6 feature matrix (item_images, section_pricing, kot_printing, qr_upi, discount_types, tax_mode, export_formats, kds, priority_support, ...) — editable by product_owner without a redeploy |
| is_active | bool | |

**`roles`** — shared lookup: `product_owner`, `tenant_admin`, `pos_user`, `waiter`, `kitchen`.

**`tenants`** — the Company Master (CLAUDE.md §4/§9)
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| tenant_code | varchar(10) unique NOT NULL, CHECK `^[A-Z0-9]{2,10}$` | short platform-assigned prefix (Phase 03), used only to compose tenant-scoped `users.user_id` (Phase 02 migration `3d908345eda4`) — see §5 |
| company_name | varchar(200) NOT NULL | |
| email | varchar(200), nullable | Phase 13 |
| phone | varchar(20), nullable | Phase 13 |
| door_no, street, city, district | varchar | Indian address format |
| state | varchar(50), CHECK ∈ `INDIAN_STATES` | |
| pincode | varchar(6), CHECK `^[1-9][0-9]{5}$` | |
| is_active | bool | |
| stock_management_enabled | bool NOT NULL, default false | tenant-wide soft-disable switch for stock-quantity tracking (Pro/Pro Max only — see `plans.features.stock_management`); toggling never touches `items.track_inventory`/`available_qty` |

### Tenant-scoped

**`tenant_locations`** — one row per hotel location, capped by `plans.max_locations`.
FK `tenant_id`. Same Indian address fields as `tenants`. A **trigger**
(`enforce_tenant_location_cap`, see below) blocks INSERT/reactivation past the cap.

**`subscriptions`** — FK `tenant_id`, `plan_id`. `status` ∈ active/suspended/cancelled,
`billing_cycle` ∈ monthly/yearly, `payment_status` ∈ paid/pending/overdue (manual flag
for now — CLAUDE.md §7), `current_period_start`/`current_period_end` dates.

**`invoices`** (Phase 14) — tenant subscription billing document, distinct from the POS
`bills` table (which bills a tenant's own customers, not the tenant itself).
| column | type | notes |
|---|---|---|
| tenant_id | uuid FK | |
| subscription_id | uuid FK → subscriptions, **nullable** | invoice can outlive/precede a subscription row |
| invoice_number | varchar(30) unique NOT NULL | server-generated `INV-{YYYYMM}-{seq}`, sequence resets monthly |
| amount | numeric(10,2) | single flat amount — plans are flat-priced, no line-item breakdown |
| status | varchar(20), CHECK ∈ draft/sent/paid/overdue | `overdue` is **never persisted** — computed from `due_date < today AND status != paid` on every read (dashboard alerts + `GET /invoices/overdue`), so there's no cron that can silently stop running |
| issued_date, due_date | date | |
| paid_date | date, nullable | set by `PATCH /invoices/{id}/mark-paid` |
| description | varchar(200), nullable | e.g. "Pro Max — Aug 2026" |

Indexed on `(tenant_id, id)` (standard tenant-scoped composite) and `(due_date, status)`
for the overdue-lookup query. RLS-enabled like every other tenant-scoped table.

**`users`** — login is always by `user_id`, never email (CLAUDE.md §5).
| column | type | notes |
|---|---|---|
| tenant_id | uuid, **nullable** | NULL only for `product_owner` |
| user_id | varchar(60), **globally unique** (single unique constraint, no per-tenant partial index — Phase 02 migration `3d908345eda4`), CHECK `^[A-Za-z0-9_-]{2,60}$` | for tenant-scoped roles, composed at creation (Phase 04) as `{tenant.tenant_code}{local_handle}` — no separator, since Phase 13 (was `{tenant_code}-{local_handle}` before; pre-Phase-13 accounts keep their hyphenated id, not renamed retroactively); `product_owner` uses a bare, unprefixed value |
| password_hash | varchar(255) | bcrypt, set in Phase 02 |
| role_id | uuid FK → roles | |
| name, phone | | |
| incentive_rate | numeric(5,2), nullable | % on net sale value; meaningful only when role=`pos_user` (cashier) |
| is_active | bool | |

**`user_location_access`** — join table, FK `user_id`, `location_id`, unique
(`user_id`, `location_id`). Per-location access grants, relevant on every tier now that
every tier can have >1 location.

**`categories`** — `name_en`, `name_ta`, `icon_url` (nullable, Phase 18 — POS falls back to
a generic icon when unset; not plan-gated unlike item images), `display_order`, `is_active`.

**`items`**
| column | type | notes |
|---|---|---|
| category_id | uuid FK | |
| name_en, name_ta | | |
| image_url | nullable | Pro+ only, enforced in Phase 05 service layer |
| price | numeric(10,2) | base/default price |
| tax_class_id | uuid FK → tax_rules, nullable | |
| item_code | varchar(20), nullable, unique per tenant | POS numeric quick-entry (CLAUDE.md §9) |
| is_top_seller | bool | feeds the POS "Top Selling" tab |
| is_combo_tile | bool | Meals/Thali-style combo — rendered as an oversized POS tile (CLAUDE.md §9) |
| track_inventory | bool, default false | soft stock tracking opt-in per item (CLAUDE.md §11) — free/always-on on every plan tier, predates plan-gating |
| available_qty | int, nullable | only meaningful while `track_inventory=true`; every change is logged to `stock_ledger` |
| is_active | bool | |

**`stock_ledger`** — audit trail for every `items.available_qty` change (extends the
above, CLAUDE.md §11). `item_id`, `location_id` (nullable — items aren't
location-scoped, only populated for `kot_deduction` rows where the triggering order's
location is meaningful), `change_qty` (signed int, before/after delta), `reason` ∈
`manual_set`/`kot_deduction`/`restock`, `reference_order_id`/`reference_bill_id` (both
nullable — `kot_deduction` populates `reference_order_id` since deduction fires at
KOT-send, before any bill exists; `reference_bill_id` is unused in this phase, kept
for schema completeness).

**`seating_sections`** — AC / Non-AC / Rooftop / Family / Takeaway / Online Delivery
(CLAUDE.md §9/§11). `name_en`, `name_ta`, `is_seating` (false for Takeaway/Online
Delivery — these skip table assignment in POS), `display_order`, `is_active`.

**`item_section_prices`** — per-item, per-section price override.
`item_id`, `section_id`, `price`; unique (`item_id`, `section_id`). Absence of a row
means the resolved price falls back to `items.price`. This is deliberately per-item, not
a blanket "+X% for AC" markup (CLAUDE.md §6/§11).

**`waiters`** — `location_id` FK, `waiter_number` (unique per tenant+location), `name`,
`phone`, `incentive_rate` (% on net sale value), `is_active`.

**`tables`** — `location_id`, `section_id` FK (**required** — only `is_seating=true`
sections are selectable), `table_number` (unique per tenant+location),
`seating_capacity`. `status` is declared on the model/response but is never written —
it's computed on read as free/occupied from whether the table has any `orders` row
with `status='open'` (Phase 19), so it can't drift out of sync with actual order state.

**`orders`** — the server-persisted "cart" (CLAUDE.md §11). `location_id`, `table_id`
(nullable — null for non-seating sections), `section_id` (always set — drives price
resolution), `waiter_id` (nullable), `pos_user_id` (cashier-of-record, NOT NULL),
`status` ∈ open/held/billed, `hold_label`, `party_label` (nullable varchar(30) —
distinguishes concurrent customers/bills at the same table, Phase 19, CLAUDE.md §11).
Values are "Customer-1"/"Customer-2"/… as of Phase 21 (was "Party 1"/"Party 2" under
the original Phase 19 UI — the column itself didn't change, only what the frontend
writes into it, so old and new label styles can coexist harmlessly in historical
data). Indexed on (`tenant_id`, `status`) for the recall list query. Partial unique
index `uq_orders_open_table_party` on (`tenant_id`, `table_id`, `party_label`) WHERE
`status='open' AND table_id IS NOT NULL AND party_label IS NOT NULL` — stops two open
customers at the same table from colliding on the same label, while leaving
non-seating orders and single-customer (label-less) orders unconstrained.

**`order_items`** — `order_id`, `item_id`, **`unit_price`** (snapshotted at add-time from
the section-resolved price — later item/section-price edits never retroactively change
an open/held order line), `quantity` (CHECK > 0), `notes`, `is_kot_sent` (repeat-KOT
tracking, Phase 08).

**`kot_tickets`** — `order_id`, `ticket_number` (unique per tenant), `status` ∈
new/preparing/ready.

**`kot_ticket_items`** — links a ticket to the specific `order_items` it fired (supports
repeat-KOT for add-on items ordered after the first ticket). `kot_ticket_id`,
`order_item_id`, `quantity`.

**`bills`** — a finalized order. Everything below is **snapshotted at bill time**, not
just referenced, so a reprint stays correct even if table/waiter/item master data
changes later.
| column | type | notes |
|---|---|---|
| location_id, order_id (unique) | | |
| bill_number | varchar(30), unique per tenant | |
| table_id | nullable | |
| section_id | NOT NULL | printed next to the table number (CLAUDE.md §9/§10) |
| waiter_id | nullable | |
| party_label | nullable varchar(30) | snapshotted from `orders.party_label` at finalize time (Phase 21), e.g. "Customer-2" — same immutable-history treatment as `table_id`/`section_id`/`waiter_id` |
| pos_user_id | NOT NULL | cashier-of-record |
| subtotal, discount_amount | numeric(10,2) | |
| cgst_amount, sgst_amount | numeric(10,2) | **always two distinct columns**, never a merged "GST" amount (CLAUDE.md §9) |
| round_off_amount | numeric(10,2), signed | explicit rounding delta to the nearest ₹1, always shown on print, never silently absorbed |
| grand_total | numeric(10,2) | |
| waiter_incentive_amount, cashier_incentive_amount | numeric(10,2), nullable | informational only — never printed on the customer bill |

**`bill_items`** — `bill_id`, `item_id`, `name_en_snapshot`/`name_ta_snapshot` (frozen at
bill time), `unit_price`, `quantity`, `line_total`.

**`payments`** — split payment lines. `bill_id`, `method` ∈ upi/cash/card (CLAUDE.md §9
orders these UPI-first in the UI), `amount`.

**`tax_rules`** — `name`, **`cgst_rate`**, **`sgst_rate`** (always two distinct rate
columns, never a single merged GST rate — CLAUDE.md §9), `is_default`, `is_active`. Lite
tenants use one (their default) row; Pro/Pro Max can define several and assign per item
via `items.tax_class_id`.

**`discount_rules`** — `name`, `type` ∈ flat_percent/item_level/coupon, `value`,
`coupon_code` (nullable, unique per tenant when set), `is_active`.

**`printers`** — `location_id`, `name`, `target` ∈ kot/bill, `printer_type` ∈
thermal/dotmatrix, `connection_type` ∈ network/usb/local_agent/wifi/bluetooth (wifi +
bluetooth added Phase 15), `connection_details` (jsonb — `{ip_address, port}` for
network/wifi, `{device_name}` for bluetooth), `paper_width_mm` (int, nullable — Phase
15; UI offers 58/80/241mm presets or free entry, not a CHECK constraint since actual
hardware varies).

**`hotel_master`** — one row per `tenant_location` (unique `location_id`). `name`, same
Indian address fields as `tenants`, `phone`, `gstin` (CHECK format), `logo_url`,
`upi_id`, `show_tamil_names` (controls the **printed** KOT/bill only — the POS
staff-facing grid always shows English+Tamil together regardless, CLAUDE.md §9).

**`audit_log`** — `user_id` (nullable), `action`, `entity_type`, `entity_id`, `details`
(jsonb). Manual price overrides/discounts above a configurable threshold (CLAUDE.md §11).

## Migrations (in order)

1. **`initial schema`** — all 25 tables above via SQLAlchemy autogenerate.
2. **`seed plans and roles`** — Lite/Pro/Pro Max rows (matching CLAUDE.md §6/§7 exactly,
   including `max_users`/`max_locations`) and the five `roles` rows.
3. **`tenant location cap trigger`** — `enforce_tenant_location_cap()` + a
   `BEFORE INSERT OR UPDATE OF is_active, tenant_id` trigger on `tenant_locations`:
   looks up the tenant's active subscription's `plan.max_locations`, counts currently
   active locations for that tenant, and raises if the new/reactivated row would exceed
   the cap. DB-level backstop behind the Phase 04-style service-layer check.
4. **`row level security policies`** — enables + **forces** RLS on all 22 tenant-scoped
   tables (`tenants`/`plans`/`roles` excluded — no `tenant_id` column). Policy:
   ```sql
   tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
   OR current_setting('app.is_platform_admin', true) = 'true'
   ```
   `app.current_tenant_id` is set per-request by `require_tenant_scope` (Phase 02) for
   tenant-scoped endpoints; `app.is_platform_admin` is set to `'true'` by a
   `require_platform_scope` dependency for `product_owner`-only endpoints that need
   cross-tenant visibility. Neither var set (the default) means the policy evaluates to
   false — **fails closed**, not open, if a route ever forgets to wire one of the two
   dependencies. `FORCE ROW LEVEL SECURITY` is required because the app's DB role is
   also the table owner (it ran the migrations), and table owners bypass RLS by default
   in Postgres — without `FORCE`, the policy would silently do nothing.
5. **`create non-superuser app role`** — creates `kotmate_app` (`NOSUPERUSER`) and grants
   it DML on all tables. **This one is load-bearing, not cosmetic**: the default
   docker-compose Postgres bootstrap role (`kotmate`) is a superuser, and superusers
   bypass RLS unconditionally regardless of `FORCE` — confirmed empirically while
   writing this phase's smoke tests, an unscoped INSERT went through silently. Migrations
   keep running as `kotmate` (`DATABASE_URL`); the app connects as `kotmate_app`
   (`APP_DATABASE_URL`, wired in `app/db/session.py`) so RLS is actually enforced in
   every environment, not just production if someone remembers to configure it there.
6. **`tenant code and global unique user id`** (Phase 02) — adds `tenants.tenant_code`
   (backfilled for any pre-existing rows) and replaces the two per-tenant/platform
   partial unique indexes on `users.user_id` with one global unique constraint, so a
   single-field login form (CLAUDE.md §5) can always resolve to exactly one account. See
   `users`/`tenants` table notes above for the resulting column shapes.

*(Several Phase 04-12 migrations — waiter login linking, items trigram search index,
items track_inventory/available_qty, bills status check constraint, platform settings
singleton — are omitted from this numbered list for brevity; see `alembic/versions/`
for the full chain. Resuming the list for the manual-testing-fix backlog phases:)*

7. **`tenant email phone`** (Phase 13) — adds `tenants.email`/`tenants.phone` (both
   nullable), captured at tenant creation and editable via `PATCH /platform/tenants/{id}`.
8. **`create invoices table`** (Phase 14) — the `invoices` table above, including its own
   RLS enable/force/policy statements (the original `row level security policies`
   migration predates this table's existence, so it couldn't have covered it).
9. **`printer width and wifi/bluetooth connection types`** (Phase 15) — adds
   `printers.paper_width_mm`, and widens the `connection_type` CHECK constraint from
   network/usb/local_agent to also allow wifi/bluetooth.
10. **`category icon url`** (Phase 18) — adds `categories.icon_url` (nullable).
11. **`order party label`** (Phase 19, revision `5a1c3e8f2d67`) — adds `orders.party_label`
    (nullable varchar(30)) and the partial unique index `uq_orders_open_table_party` on
    (`tenant_id`, `table_id`, `party_label`) WHERE `status='open' AND table_id IS NOT
    NULL AND party_label IS NOT NULL`.
12. **`pro plan item import`** (Phase 21, revision `9c46b3480166`) — data-only: JSONB-merges
    `item_import: true` onto the seeded `pro` plan's `features` (Pro tenants now get Item
    Master CSV import, not just export; only Lite remains without it).
13. **`bill party label`** (Phase 21, revision `12432d67bb20`) — adds `bills.party_label`
    (nullable varchar(30)), snapshotted from `orders.party_label` at finalize time.
14. **`stock ledger and tenant toggle`** (Phase 22, revision `5d52cf46dd81`) — adds the
    `stock_ledger` table (including its own RLS enable/force/policy statements, same
    `dd586dfba4be`-predates-this-table reason as `invoices`) and
    `tenants.stock_management_enabled` (bool, default false).
15. **`stock management plan feature`** (Phase 22, revision `ffa2fb832bd7`) —
    data-only: JSONB-merges `stock_management: true` onto the seeded `pro`/`pro_max`
    plans' `features` (same pattern as revision 12's `item_import` change).

### Gotcha for Phase 02: setting the RLS session vars

`SET LOCAL x = :param` **does not accept bind parameters in Postgres** — it's a syntax
error, not a silent no-op. `require_tenant_scope`/`require_platform_scope` must use
`set_config()` instead, which is a normal function call and takes parameters fine:
```sql
SELECT set_config('app.current_tenant_id', :tenant_id, true)   -- true = tx-scoped, like SET LOCAL
SELECT set_config('app.is_platform_admin', 'true', true)
```
