# Architecture — StoreMate TN

## High-level
```
┌────────────┐      HTTPS       ┌──────────────┐      asyncpg      ┌────────────┐
│  React SPA │ ───────────────▶ │   FastAPI     │ ─────────────────▶│ PostgreSQL │
│ (Vite,TS)  │ ◀─────────────── │  (uvicorn)    │ ◀─────────────────│            │
└────────────┘   JSON / JWT     └──────┬───────┘                    └────────────┘
                                         │ APScheduler (background jobs)
                                         ▼
                                  Low-stock check,
                                  scheduled reports
```

Single Docker Compose stack: `frontend` (nginx-served static build),
`backend` (uvicorn/gunicorn), `db` (postgres), `nginx` (reverse proxy + TLS
via certbot), all behind one Hostinger VPS. No external message broker.

## Multi-tenancy
- Every business table has `tenant_id UUID NOT NULL`.
- `tenant_id` is resolved from the JWT on every request and injected by
  `middleware/tenant_context.py`; repositories always filter by it — never
  optional.
- `product_owner` role bypasses tenant scoping and instead operates on the
  `tenants`, `subscriptions`, `plans` tables directly.

## Request flow (typical POS sale)
1. `pos_user` authenticates → JWT contains `user_id, tenant_id, store_id, role`.
2. Frontend loads item cache (`/items?store_id=`) with TanStack Query,
   cached for fast keyboard/barcode search.
3. Cart built client-side; on checkout, POST `/bills` with line items —
   **server recalculates tax/discount/total authoritatively**, never trusts
   client totals.
4. `services/billing_service.py` writes `bills` + `bill_items`, decrements
   `stock`, triggers low-stock check (Pro/Pro Max) via background task.
5. Response includes a print-ready payload; frontend renders to the
   configured printer profile (ESC/POS commands for thermal, plain-text
   ESC/P layout for dot-matrix).

## Printer strategy
Browser sandboxing prevents direct raw USB/serial printing from a normal
web page reliably across all POS hardware, so StoreMate supports two paths,
both configured under Settings → Printer:
1. **WebUSB/WebSerial (Chrome/Edge only, desktop):** for supported thermal
   printers, print directly from the browser using an ESC/POS command
   builder.
2. **Local Print Agent (fallback, all printers incl. dot-matrix):** a tiny
   local Flask helper (`scripts/local_print_agent.py`, reference
   implementation) that binds to `127.0.0.1:9743` and accepts
   `POST /print` with `{format: "escpos", data_base64}` or `{format: "text",
   data}`, sending the bytes straight to a Windows printer's RAW datatype
   via `pywin32` (`win32print`). Required for dot-matrix / older LPT-USB
   printers that have no browser API path. This keeps the core app 100%
   web-based while still supporting legacy hardware common in TN retail.
   The frontend's print dispatch (`frontend/src/features/pos/printDispatch.ts`)
   tries WebUSB first for `thermal_*` profiles with `connection=webusb`,
   falling back to this agent on failure or for `connection=local_agent` /
   `dot_matrix` profiles. The agent's URL is configurable via
   `VITE_LOCAL_PRINT_AGENT_URL` (default `http://localhost:9743`).

## Scalability path (documented, not built in v1)
- Shared-schema multi-tenancy can be split to schema-per-tenant or a
  dedicated DB per large chain customer later — repository layer already
  isolates all queries by `tenant_id`, so this is a migration, not a
  rewrite.
- Read replicas can be added in front of reporting queries if a tenant's
  data volume grows large (Pro Max multi-store).
- Stateless FastAPI containers behind Nginx can be horizontally scaled on
  Hostinger VPS/Cloud as needed; session state lives only in JWT + DB.
