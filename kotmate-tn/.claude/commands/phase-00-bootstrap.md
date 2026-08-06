# /phase-00-bootstrap

Read `CLAUDE.md` fully before starting.

## Goal
Scaffold the monorepo skeleton for KOTMate TN: backend (FastAPI) and frontend (React/Vite/TS/Tailwind) projects, Docker Compose for local dev, base configs, linting, and env templates. No business features yet.

## Scope
1. **Backend**
   - `backend/app/main.py` — FastAPI app factory, CORS, health check `/api/v1/health`.
   - `backend/app/core/config.py` — Pydantic Settings (DATABASE_URL, JWT_SECRET, ENV, CORS_ORIGINS).
   - `backend/requirements.txt` — fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, python-jose, passlib[bcrypt], python-multipart, websockets.
   - `backend/Dockerfile`, `backend/.env.example`.
   - `backend/app/db/session.py` — async engine + sessionmaker + `get_db` dependency.
2. **Frontend**
   - `npm create vite@latest frontend -- --template react-ts` equivalent structure.
   - Install & configure Tailwind CSS + shadcn/ui base setup.
   - `frontend/src/lib/api.ts` — axios/fetch client with base URL from `VITE_API_URL`, JWT interceptor stub.
   - `frontend/src/locales/en.json` and `ta.json` with placeholder keys; wire i18next.
   - Base responsive `AppShell` layout with breakpoint-aware sidebar (desktop) / bottom-nav (mobile) stub.
3. **Infra**
   - `docker-compose.yml` — postgres:15, backend, frontend (dev + prod build stages), nginx reverse proxy stub for prod.
   - Root `.gitignore` (node_modules, __pycache__, .env, dist, .venv).
   - `README.md` with local dev run instructions.
4. GitHub Actions `ci.yml` — lint + build check for both apps (can be minimal).

## Acceptance Criteria
- `docker compose up` boots postgres + backend (`/api/v1/health` returns 200) + frontend dev server.
- `frontend` renders a blank AppShell with a language toggle (en/ta) that swaps two placeholder strings.
- No business logic yet — this phase is pure scaffolding.
