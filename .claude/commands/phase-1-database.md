---
description: Phase 1 - PostgreSQL schema, SQLAlchemy models, Alembic migrations
---

# Phase 1 — Database Layer

Read `CLAUDE.md` and `docs/DATABASE_SCHEMA.md` fully before starting.
Implement the schema exactly as documented there. If you find a necessary
deviation, update `docs/DATABASE_SCHEMA.md` in the same phase and explain
why in your summary.

## Tasks

1. Set up async SQLAlchemy 2.0 engine/session in `backend/app/core/db.py`
   (async engine, `AsyncSession` factory, `get_db` FastAPI dependency).
2. Create all models in `backend/app/models/` — one file per aggregate
   (`plan.py`, `tenant.py`, `subscription.py`, `store.py`, `user.py`,
   `category.py`, `item.py`, `stock.py`, `tax_profile.py`,
   `discount_rule.py`, `bill.py`, `printer_profile.py`,
   `company_settings.py`, `notification.py`, `audit_log.py`).
   - Use `UUID` PKs (`server_default=text("gen_random_uuid()")`), enable
     the `pgcrypto` extension in the first migration.
   - Every tenant-scoped table has `tenant_id` FK with `ondelete="CASCADE"`
     and an index.
   - Monetary fields are `BigInteger` (paise).
   - Use SQLAlchemy `Enum` types for role/status/type fields listed in the
     schema doc.
3. Configure Alembic (`backend/alembic/env.py`) for async engine + autogen
   support, reading `DATABASE_URL` from settings.
4. Generate the initial migration covering the entire schema, plus indexes
   listed in `docs/DATABASE_SCHEMA.md §Indexes`.
5. Write `scripts/seed_dev_data.py` — creates one demo tenant ("Demo Store
   Chennai"), the 3 plans (lite/pro/pro_max with the INR prices from
   `docs/SUBSCRIPTION_TIERS.md`, stored as paise), a product_owner user, an
   admin user, a pos_user, a couple of categories and ~15 sample FMCG items
   (rice, oil, biscuits, soap, etc. — realistic TN kirana stock) with
   Tamil names filled in, and starter stock quantities.
6. Cross-platform runner: `scripts/seed_dev_data.ps1` and
   `scripts/seed_dev_data.sh` both simply call
   `python scripts/seed_dev_data.py` (Windows/Docker Desktop friendly per
   CLAUDE.md §3).

## Definition of Done
- [ ] `alembic upgrade head` runs clean against a fresh `db` container
- [ ] All tables from `docs/DATABASE_SCHEMA.md` exist with correct types/FKs
- [ ] Seed script runs and populates demo tenant + plans + users + items + stock
- [ ] `alembic downgrade base` and re-upgrade both work without error
- [ ] No model uses `Float`/`Numeric` for money — paise integers only
