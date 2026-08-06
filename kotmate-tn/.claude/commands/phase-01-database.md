# /phase-01-database

Read `CLAUDE.md` §4, §8 before starting.

## Goal
Design and implement the full multi-tenant PostgreSQL schema via SQLAlchemy models + Alembic migrations. This is the foundation every later phase builds on — be thorough.

## Scope
1. Write `docs/db-schema.md` first: ERD description (tables, columns, FKs, indexes) covering:
   - `tenants` (company name + Indian-format address: `door_no`, `street`, `city`, `district`, `state` enum, `pincode` 6-digit — the Company Master), `tenant_locations` (per-hotel name + same Indian-format address fields; capped by `plans.max_locations`: Lite=1, Pro=2, Pro Max=5), `plans` (incl. `max_users`, `max_locations`), `subscriptions`
   - `roles`, `users` (tenant_id nullable for product_owner; `user_id` — unique login handle, unique per tenant or platform-wide for product_owner, **never email**; `incentive_rate` nullable, used when role=`pos_user`), `user_location_access`
   - `categories`, `items` (name_en, name_ta, image_url nullable, price, tax_class_id, `item_code` nullable short unique-per-tenant code for POS quick-entry, `is_top_seller`, `is_combo_tile` — meals/thali-style combo items rendered larger on POS per CLAUDE.md §9, `is_active`)
   - `seating_sections` (name_en, name_ta, `is_seating` bool — false for Takeaway/Online Delivery which skip table assignment, display_order, is_active)
   - `item_section_prices` (item_id, section_id, price — per-item override; unique on (item_id, section_id); absence means fall back to `items.price`)
   - `waiters` (waiter_number, name, phone, incentive_rate, is_active), `tables` (table_number, location_id, `section_id` FK to seating_sections, seating_capacity, status)
   - `orders`, `order_items` (unit_price snapshotted at add-time from the resolved section price, so later master-price edits never retroactively change an open/held order), `kot_tickets`, `kot_ticket_items`
   - `bills` (incl. `round_off_amount` — signed, the delta applied to round the grand total to the nearest ₹1), `bill_items`, `payments` (supports split payment)
   - `tax_rules` (CGST and SGST tracked as distinct rate rows, never a single merged "GST" rate — both must render as separate lines per CLAUDE.md §9)
   - `printers`, `hotel_master` (per-location, same Indian-format address fields as `tenant_locations`, plus GSTIN — validate the address `state` matches the GSTIN's embedded state code)
   - `audit_log`
2. Implement SQLAlchemy 2.0 async models under `backend/app/models/`, one file per domain, all tenant-scoped tables carrying `tenant_id` FK + composite index `(tenant_id, id)`.
3. Alembic setup (`backend/alembic/`), initial migration creating all tables + seed migration for default `plans` (Lite/Pro/Pro Max from CLAUDE.md §6/§7, including `max_users`/`max_locations`) and default `roles`. Seed each new tenant with default `seating_sections` rows (AC, Non-AC, Rooftop, Family, Takeaway [`is_seating=false`], Online Delivery [`is_seating=false`]) on tenant creation (Phase 03), not in this global seed migration.
4. Add Postgres Row-Level-Security policies (defense-in-depth) as a follow-up migration, gated by a settable `app.current_tenant_id` session variable.
5. `backend/app/db/base.py` — declarative base + naming convention for constraints.
6. DB-level constraint/trigger (or service-layer check, whichever is cleaner in SQLAlchemy 2.0 async) enforcing `count(tenant_locations) <= plans.max_locations` on insert — mirrors the seat-cap pattern from Phase 04.

## Acceptance Criteria
- `alembic upgrade head` runs clean against the docker postgres.
- `plans` table pre-populated with Lite/Pro/Pro Max rows matching CLAUDE.md feature flags, including `max_users`/`max_locations` (store the rest as JSONB `features` column for extensibility).
- A quick script/test inserts a tenant + location + user (with `user_id`, not email) and reads it back through async session.
- A quick script/test inserts an item with no `item_section_prices` row and confirms the resolved price falls back to `items.price`; inserting an override row for one section changes only that section's resolved price.
