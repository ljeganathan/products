# KOTMate TN

Multi-tenant, subscription-based Hotel/Restaurant KOT & Billing SaaS for Tamil Nadu.
React + Vite + TypeScript frontend, FastAPI + PostgreSQL backend, deployed on Hostinger.

## Getting Started with Claude Code

1. Unzip this project and open the folder in your terminal.
2. Run `claude` (Claude Code CLI) inside this folder.
3. Read `CLAUDE.md` first — it's the full architecture blueprint and is auto-loaded as context by Claude Code.
4. Execute phases **in order**, one at a time, verifying each before moving to the next:

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

Each `.claude/commands/phase-*.md` file is a self-contained scope with acceptance criteria — Claude Code will treat these as slash commands automatically since they live under `.claude/commands/`.

See `docs/eta-roadmap.md` for time estimates and `docs/subscription-tiers.md` for the pricing/feature matrix this build implements.

## Local Development

**Everything via Docker (recommended):**

```
docker compose up
```

- Backend: http://localhost:8000/api/v1/health → `{"status": "ok"}`
- Frontend: http://localhost:5173
- Postgres: localhost:5433 (`kotmate` / `kotmate`) — mapped off the default 5432 to avoid clashing with other local Postgres containers

**Running the apps natively instead:**

Backend:
```
cd backend
python -m venv .venv && .venv\Scripts\activate   # or `source .venv/bin/activate` on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env    # adjust DATABASE_URL to point at your local Postgres
uvicorn app.main:app --reload
```

Frontend:
```
cd frontend
npm install
cp .env.example .env
npm run dev
```

**Tests & lint:**
```
cd backend && pytest && ruff check .
cd frontend && npm run lint && npm run build
```

Production build (built frontend served by nginx, proxying to the backend) — not the default `docker compose up` flow, wired up fully in Phase 12:
```
docker compose --profile prod up nginx
```

## Manual Testing

`docs/manual-testing-guide.md` is a phase-by-phase checklist for testing in a browser,
backed by a reusable seed script (`python -m scripts.seed_demo_data`, run from
`backend/`) that creates one demo hotel per subscription tier with realistic sample
data — items, staff, printers, and finalized bills. Safe to re-run any time.
