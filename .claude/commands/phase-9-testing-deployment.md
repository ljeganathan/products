---
description: Phase 9 - Test coverage, Hostinger Docker Compose deploy, Nginx, backups, CI/CD
---

# Phase 9 — Testing, Hardening & Deployment (Hostinger)

Read `docs/ARCHITECTURE.md` fully. This phase makes the app production-safe
and ships it.

## Tasks

1. **Test coverage pass**: fill gaps across backend (`pytest --cov`) and
   frontend (component/unit tests for POS totals engine, RBAC guards,
   i18n). Target meaningful coverage of billing math, auth, and plan-limit
   logic specifically — these are the modules where a bug costs money or
   security.
2. **Security hardening**:
   - Rate limiting on `/auth/login` (basic in-memory or DB-backed
     lockout after N failed attempts).
   - CORS locked to the real frontend origin(s) in production config.
   - All secrets confirmed to come from environment, never committed
     (double-check `.gitignore` per CLAUDE.md §3).
   - SQL injection/XSS spot-check on any raw query or dangerouslySetInnerHTML usage (should be none).
3. **`docker-compose.prod.yml`**: production stack — `nginx` (TLS via
   certbot, serves the built frontend static files, reverse-proxies
   `/api` to backend), `backend` (gunicorn+uvicorn workers), `db` (with a
   named volume + documented backup path), all with restart policies.
4. **Hostinger deployment guide**: `docs/DEPLOYMENT.md` — step-by-step for
   a Hostinger VPS: initial server setup, Docker install, cloning the repo,
   `.env` production values, `docker compose -f docker-compose.prod.yml up
   -d --build`, certbot TLS issuance, DNS pointing instructions, and a
   simple zero-downtime-ish redeploy script (`scripts/deploy.sh` +
   Windows-friendly notes since day-to-day dev is on Windows even though
   the VPS itself is Linux).
5. **Backups**: `scripts/backup_db.sh` (pg_dump to a local/remote target,
   cron-friendly) and a restore runbook in `docs/DEPLOYMENT.md`.
6. **CI/CD**: extend `.github/workflows/ci.yml` with a `deploy` job
   (SSH to Hostinger VPS on `main` branch merge, pull + rebuild) —
   guarded behind a manual approval or tag-based trigger since this is a
   paid customer-facing app.
7. **Final smoke test checklist**: log in as each of the 3 roles, complete
   a full POS sale, print a thermal preview, print a dot-matrix preview,
   change a tenant's plan and confirm gating updates immediately, trigger
   a low-stock notification, export a sales report — all against the
   deployed environment.

## Definition of Done
- [ ] `docker compose -f docker-compose.prod.yml up -d --build` succeeds on a clean Hostinger VPS
- [ ] HTTPS works via certbot with auto-renewal configured
- [ ] Backup script produces a restorable dump; restore runbook tested at least once
- [ ] CI runs tests on every PR and deploy job is gated appropriately
- [ ] Full smoke test checklist passes against the live deployment
- [ ] `docs/DEPLOYMENT.md` is complete enough that a new team member could deploy from scratch
