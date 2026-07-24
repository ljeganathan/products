---
description: Phase 0 - Repo scaffolding, tooling, Docker Compose, CI skeleton
---

# Phase 0 — Project Setup

Read `CLAUDE.md` fully before starting. This phase produces a runnable
empty-shell app: backend health endpoint + frontend "hello" screen, both in
Docker Compose, before any real feature work begins.

## Tasks

1. **Backend skeleton**
   - `backend/requirements.txt`: fastapi, uvicorn[standard], sqlalchemy>=2.0,
     asyncpg, alembic, pydantic>=2, pydantic-settings, python-jose[cryptography],
     passlib[bcrypt], python-multipart, apscheduler, httpx, pytest, pytest-asyncio.
   - `backend/app/main.py`: FastAPI app, CORS for the frontend origin, a
     `/health` endpoint, versioned router mount at `/api/v1`.
   - `backend/app/core/config.py`: Pydantic Settings reading from `.env`
     (DATABASE_URL, JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MIN,
     REFRESH_TOKEN_EXPIRE_DAYS, CORS_ORIGINS, ENV).
   - `backend/.env.example` with all keys above (no real secrets).
   - `backend/Dockerfile` (python:3.11-slim, non-root user, uvicorn entrypoint).
   - `backend/.gitignore` (venv, __pycache__, .env, *.pyc).

2. **Frontend skeleton**
   - Vite + React + TypeScript project in `frontend/`.
   - Install: react-router-dom, zustand, @tanstack/react-query, axios,
     i18next, react-i18next, tailwindcss, shadcn/ui deps, lucide-react.
   - Tailwind configured; base design tokens placeholder (finalized in
     Phase 4 using `frontend-design` best practice — colorful, modern retail
     feel, not generic admin-dashboard grey).
   - `frontend/.env.example` (VITE_API_BASE_URL).
   - `frontend/Dockerfile` (multi-stage: build with node, serve with nginx).
   - `frontend/.gitignore` (node_modules, dist, .env).
   - A single landing route rendering "StoreMate TN — build in progress"
     that fetches `/health` from the backend to prove connectivity.

3. **Docker Compose**
   - `docker/docker-compose.yml` at repo root reference (or root
     `docker-compose.yml`) with services: `db` (postgres:15, named volume,
     healthcheck), `backend`, `frontend`, `nginx` (reverse proxy, only
     active in a `docker-compose.prod.yml` override — keep dev compose
     simple with frontend dev server + backend on separate ports).
   - `docker-compose.yml` for local dev (hot reload both sides).
   - `docker-compose.prod.yml` override for the Hostinger deployment shape
     (used in Phase 9).

4. **CI skeleton**
   - `.github/workflows/ci.yml`: on push/PR — backend (ruff + mypy optional +
     pytest), frontend (eslint + tsc --noEmit + vite build). No deploy step
     yet (Phase 9).

5. **Root files**
   - Root `README.md`: project overview, how to run locally
     (`docker compose up`), links to `CLAUDE.md` and `docs/`.
   - Root `.gitignore` covers editor/OS junk only — each service keeps its
     own for language-specific ignores (per CLAUDE.md §3).

## Definition of Done
- [ ] `docker compose up` starts db + backend + frontend with no errors
- [ ] `GET http://localhost:8000/api/v1/health` returns `{"status":"ok"}`
- [ ] Frontend dev server loads and shows successful backend connectivity
- [ ] `docker compose down -v && docker compose up` works from clean state
- [ ] CI workflow file is valid YAML and would run on push
