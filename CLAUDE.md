# CLAUDE.md — StoreMate TN (Retail POS SaaS)

This file is the single source of truth for every Claude Code session on this
repository. Read this file completely before writing any code. Follow it
exactly. Do not deviate from the architecture, naming, or folder structure
defined here without updating this file first.

## 0. Product Summary

**Product name:** StoreMate TN
**One-liner:** A subscription-based, multi-tenant Point-of-Sale and
inventory platform for Tamil Nadu FMCG retail stores (kirana/supermarket),
usable on desktop and tablet, with Tamil + English UI, barcode/keyboard-first
billing, and TN-GST compliant invoicing.

**Primary users**
| Role | Description |
|---|---|
| `product_owner` | Anthropic-of-this-app. You. Manages tenants, subscriptions, plan upgrades/downgrades, global maintenance, feature flags. One per platform (or a small internal team). |
| `admin` | Store owner / store manager for a tenant. Manages users, stock, settings, reports for their store(s). |
| `pos_user` | Cashier / billing staff. Access limited to POS screen, saved-bill search, and their own shift reports. |

**Multi-tenancy model:** Single database, `tenant_id` on every business table
(shared schema, row-level isolation). Chosen over schema-per-tenant for
Hostinger VPS cost/simplicity; documented as swappable later (see
`docs/ARCHITECTURE.md`).

## 1. Tech Stack (fixed — do not substitute)

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript, TailwindCSS, shadcn/ui, Zustand (state), TanStack Query, React Router v6, i18next (Tamil/English) |
| Backend | FastAPI (Python 3.11+), Pydantic v2, SQLAlchemy 2.0 (async), Alembic migrations |
| Database | PostgreSQL 15+ |
| Auth | JWT (access + refresh), passlib[bcrypt], role & plan-based route guards |
| Realtime/low-stock alerts | FastAPI background tasks + APScheduler (no external broker needed at this scale) |
| Printing | Browser-side ESC/POS via WebUSB/WebSerial fallback to a lightweight local print-agent (documented in Phase 5); PDF fallback for dot-matrix via raw ESC/P text templates |
| Deployment target | Hostinger VPS, Docker Compose, Nginx reverse proxy, Let's Encrypt |
| CI | GitHub Actions (lint, type-check, test) |

Do not introduce Redis, Kafka, microservices, Kubernetes, or GraphQL. This is
an intentionally boring, cost-efficient monolith-with-clean-layers so it runs
comfortably on a modest Hostinger VPS.

## 2. Repository Layout

```
storemate-tn/
├── CLAUDE.md                  # this file
├── .claude/commands/          # phase-wise slash commands, run in order
├── docs/                      # architecture, schema, subscription tiers, API contracts
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/              # config, security, db session, deps
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── api/v1/             # routers, one file per resource
│   │   ├── services/           # business logic (billing, tax, stock, subscription)
│   │   ├── repositories/       # DB access layer (repository pattern)
│   │   ├── middleware/         # tenant resolution, plan-limit enforcement, audit log
│   │   ├── utils/
│   │   └── tests/
│   ├── alembic/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/               # route-level screens
│   │   ├── features/            # pos, stock, settings, users, subscription (feature-sliced)
│   │   ├── components/          # shared/reusable UI
│   │   ├── layouts/
│   │   ├── store/                # zustand slices
│   │   ├── api/                  # typed API client
│   │   ├── i18n/                  # en.json, ta.json
│   │   └── styles/
│   └── public/
├── docker/                    # Dockerfiles + nginx.conf
├── scripts/                   # db seed, backup, deploy helpers
└── .github/workflows/
```

## 3. Coding Standards (non-negotiable)

- **No placeholders, no TODOs, no stub functions.** Every function Claude
  Code writes in a phase must be complete and runnable at the end of that
  phase.
- Backend: full type hints, Pydantic v2 schemas for every request/response,
  async SQLAlchemy sessions, repository pattern (routers → services →
  repositories → models). No business logic in routers.
- Frontend: TypeScript strict mode, no `any` unless justified in a comment,
  feature-sliced folders, shared UI in `components/`, all API calls typed.
- Every list/table endpoint: pagination + filtering + `tenant_id` scoping by
  default via middleware, never manually per-router.
- Every currency value: stored as integer paise (₹ × 100) to avoid float
  rounding bugs; displayed formatted in the UI layer only.
- Every migration goes through Alembic — never hand-edit the DB schema.
- Windows + Docker Desktop is the target dev machine — no bash-only tooling
  in `scripts/`; provide `.ps1` or cross-platform Python scripts alongside
  any `.sh` file.
- Secrets: `.env` files are used for local dev only (each service has its
  own `.env.example`, real `.env` stays gitignored). Production secrets are
  injected via Hostinger/Docker Compose environment variables at deploy
  time, never committed.
- Each top-level folder (`backend/`, `frontend/`) keeps its own
  `.gitignore`; do not rely on a single root `.gitignore` for everything.
- Every phase ends with: migrations applied, backend boots, frontend boots,
  and a short manual test checklist in the command file passes.

## 4. Subscription Tiers & Feature Gating

Three plans: **Lite**, **Pro**, **Pro Max**. Enforced server-side via a
`middleware/plan_limits.py` that reads the tenant's active plan on every
request — the frontend also hides gated UI, but the backend is the source of
truth (never trust the client for entitlement checks).

See `docs/SUBSCRIPTION_TIERS.md` for the full matrix, limits, and INR
pricing. Summary:

| Feature | Lite | Pro | Pro Max |
|---|---|---|---|
| POS billing, barcode entry | ✅ | ✅ | ✅ |
| Users included | 2 (1 admin + 1 pos) | 5 | Unlimited |
| Stock master + category master | ✅ | ✅ | ✅ |
| Low-stock notifications | ❌ | ✅ | ✅ |
| Multi-store (multiple `store_id` under one tenant) | ❌ | ❌ | ✅ |
| Tamil + English UI | ✅ | ✅ | ✅ |
| Saved bill search & recall | ✅ (7 days) | ✅ (90 days) | ✅ (unlimited) |
| **Dashboard** | Today snapshot only (sales, bill count, top 5 items) | + date-range view, category/cashier breakdown, low-stock widget, trend charts | + multi-store consolidated + per-store view, customizable widgets, export dashboard as PDF |
| Reports (sales, GST, shift) | Basic (daily) | Advanced (range, export CSV) | Advanced + scheduled email reports |
| Printer profiles (thermal/dot-matrix) | 1 profile | 3 profiles | Unlimited |
| Discount rules / promotions engine | Manual bill discount only | + item-level & category discount rules | + scheduled/automatic promotions |
| API access for integrations | ❌ | ❌ | ✅ |
| Priority support | ❌ | ✅ | ✅ |

## 5. Role → Access Matrix (enforced backend + frontend)

| Screen/Action | product_owner | admin | pos_user |
|---|---|---|---|
| Platform tenant/subscription maintenance | ✅ | ❌ | ❌ |
| Platform-level dashboard (all tenants, MRR, churn, plan mix) | ✅ | ❌ | ❌ |
| Store user management (add/edit/deactivate, assign role) | ❌ (own login only) | ✅ | ❌ |
| Stock/Item/Category master | ❌ | ✅ | View-only (read) |
| Settings (tax, printer, company, language) | ❌ | ✅ | ❌ |
| Store dashboard (sales, stock, alerts — depth by plan) | ❌ | ✅ | ❌ |
| POS billing screen | ❌ | ✅ | ✅ |
| Saved bill search | ❌ | ✅ | ✅ (own shift by default, all if permitted) |
| Reports | Platform-level only | Store-level | Own-shift only |

## 6. Execution Plan — Run Phases In Order

Each phase is a slash command in `.claude/commands/`. Run them **in order**,
one at a time, in a fresh or continued Claude Code session, and verify the
"Definition of Done" checklist at the bottom of each file before moving to
the next phase. Do not skip ahead.

1. `/phase-0-setup` — repo scaffolding, tooling, Docker Compose, CI skeleton
2. `/phase-1-database` — PostgreSQL schema, SQLAlchemy models, Alembic
3. `/phase-2-backend-auth` — auth, JWT, roles, tenant middleware, plan-limit middleware
4. `/phase-3-backend-core` — item/category/stock master APIs, tax config, company settings, printer settings APIs
5. `/phase-4-frontend-foundation` — app shell, routing, auth screens, RBAC route guards, i18n setup, design system
6. `/phase-5-pos-module` — full POS screen (keyboard + barcode + touch), cart, tax/discount engine, bill save/print
7. `/phase-6-settings-module` — stock entry UI, category/item UI, settings UI, low-stock alerts UI
8. `/phase-7-subscription-billing` — product owner console, plan management, feature gating end-to-end
9. `/phase-8-dashboard-reports` — role/plan-aware dashboard, low-stock notification service, reports & exports
10. `/phase-9-testing-deployment` — test coverage, Hostinger Docker Compose deploy, Nginx, backups, CI

See `docs/*` for schema and API contract detail referenced by every phase.

## 7. Localization Rule

Every user-facing string in `pos`, `stock`, and `item/category master`
screens must go through `i18n` keys with `en` and `ta` entries — never
hardcode Tamil or English text directly in components. Language is a
**per-tenant setting** (Settings → Language) affecting item names and UI
labels; item master stores both `name_en` and `name_ta` columns for every
item/category so a store can bill in either language regardless of the
setting.

## 8. Tamil Nadu Tax Rule

Tax must be a **configurable** table (`tax_profiles`), not hardcoded GST
slabs — Tamil Nadu FMCG retail needs CGST+SGST split (intra-state) with
configurable rates per item/category (0%, 5%, 12%, 18%, 28% typical FMCG
slabs), plus support for a flat/no-tax mode for unregistered small stores.
See `docs/DATABASE_SCHEMA.md §tax_profiles`.

## 9. When Claude Code Starts Any Phase

1. Re-read this CLAUDE.md and the relevant `docs/*.md` files.
2. Read the specific phase command file fully before writing code.
3. Confirm previous phase's Definition of Done still holds (`docker compose up`, migrations current).
4. Implement completely — no partial features.
5. Update `docs/API_CONTRACTS.md` if new endpoints are added.
6. Report back a summary + the Definition of Done checklist, checked off.
