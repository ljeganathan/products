# StoreMate TN

Subscription-based Point-of-Sale & inventory platform for Tamil Nadu FMCG
retail stores. Desktop/tablet ready. Tamil + English. Built with React +
FastAPI + PostgreSQL.

## Start here

1. Read **`CLAUDE.md`** — the full architecture, standards, and role/plan
   model. This governs every Claude Code session on this repo.
2. Skim `docs/`:
   - `ARCHITECTURE.md` — system design, tenancy, printer strategy
   - `DATABASE_SCHEMA.md` — full table reference
   - `SUBSCRIPTION_TIERS.md` — Lite/Pro/Pro Max features & INR pricing
   - `API_CONTRACTS.md` — living API surface reference
3. Run phases **in order** with Claude Code, one at a time, from
   `.claude/commands/`:

   ```
   /phase-0-setup
   /phase-1-database
   /phase-2-backend-auth
   /phase-3-backend-core
   /phase-4-frontend-foundation
   /phase-5-pos-module
   /phase-6-settings-module
   /phase-7-subscription-billing
   /phase-8-dashboard-reports
   /phase-9-testing-deployment
   ```

   After each phase, verify its "Definition of Done" checklist before
   starting the next one. Don't skip ahead — later phases assume earlier
   ones are fully working.

## Local development (once Phase 0 is done)

```
docker compose up
```

- Frontend: http://localhost:5173
- Backend:  http://localhost:8000/api/v1
- API docs: http://localhost:8000/docs

## Roles

- **product_owner** — you. Manages tenants/subscriptions/maintenance (`/owner`).
- **admin** — store owner/manager. Manages users, stock, settings (`/settings`, `/stock`, `/items`, `/users`).
- **pos_user** — cashier. POS screen + saved-bill search only.

## Plans

Lite / Pro / Pro Max — see `docs/SUBSCRIPTION_TIERS.md` for the full
feature matrix and current INR pricing.
