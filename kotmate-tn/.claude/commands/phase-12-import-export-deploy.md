# /phase-12-import-export-deploy

Read `CLAUDE.md` §1-§11 (full recap) before starting — this is the final hardening + deployment phase.

## Goal
Item import/export (Pro Max import, Pro+ export), final polish, security hardening, and production deployment to Hostinger.

## Scope
1. **Import/Export**
   - `GET /api/v1/items/export` (CSV/Excel, Pro+) — includes one column per active seating section holding that item's `item_section_prices` override (blank = uses base price) for tenants with section pricing enabled.
   - `POST /api/v1/items/import` (CSV/Excel upload, Pro Max only) — validate rows (name_en required, price numeric, category must exist or auto-create option, section-price columns optional/nullable), return a row-level error report for partial failures, transactional apply.
2. **Hardening**
   - Rate limiting on auth endpoints, input validation review, RLS policy audit, secrets via `.env`/Hostinger environment config (never committed).
   - Basic automated test coverage summary across backend (pytest) and frontend (vitest) — fill gaps found in earlier phases.
   - Error monitoring hook (e.g. Sentry) as an optional env-gated integration.
3. **Deployment (Hostinger)**
   - `docker-compose.prod.yml`: nginx (TLS via certbot or Hostinger-managed cert) reverse-proxying to frontend static build + backend gunicorn/uvicorn workers; postgres either managed or containerized with a volume + backup cron.
   - Deployment runbook in `docs/deployment.md`: DNS, env vars, migration step, zero-downtime deploy notes, backup/restore steps.
   - Smoke test checklist post-deploy (login, POS order, KOT, bill print, report export) covering all three plan tiers with test tenants.

## Acceptance Criteria
- Full user journey (product owner creates tenant → tenant admin sets up hotel/items/printers → POS user bills a customer with KOT + tax + discount + split payment + print → reports reconcile) works end-to-end on the deployed Hostinger environment.
- Import a sample 50-item CSV successfully as a Pro Max tenant; partial-failure CSV shows correct row-level errors without corrupting existing data.
- Deployment runbook is followable by someone other than the original implementer.
