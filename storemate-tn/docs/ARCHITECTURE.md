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
web page reliably across all POS hardware, so StoreMate supports six paths,
all configured under Settings → Printer via a printer profile's `connection`
+ `connection_details`, and all dispatched from a single entry point,
`frontend/src/features/pos/printDispatch.ts`. Every path is built from the
same rendered bytes (`utils/escpos.ts` for thermal, `utils/dotmatrix.ts` for
dot-matrix) — only the transport differs:
1. **WebUSB (Chrome/Edge only, desktop):** for supported thermal printers
   (`connection=webusb`), prints directly from the browser using the
   ESC/POS command builder. Falls back to the Local Print Agent on failure.
2. **Local Print Agent (all printers incl. dot-matrix):** a tiny local
   Flask helper (`scripts/local_print_agent.py`, reference implementation)
   that binds to `127.0.0.1:9743` and accepts `POST /print` with
   `{format: "escpos", data_base64}` or `{format: "text", data}` (plus an
   optional `printer_name` when a till PC has more than one printer queue,
   from `connection_details.windows_printer_name`), sending the bytes
   straight to a Windows printer's RAW datatype via `pywin32`
   (`win32print`). Required for dot-matrix / older LPT-USB printers that
   have no browser API path. The agent's URL is configurable via
   `VITE_LOCAL_PRINT_AGENT_URL` (default `http://localhost:9743`).
3. **Network/WiFi (`connection=network|wifi`):** the one path dispatched
   server-side instead of from the browser, since JavaScript can't open a
   raw TCP socket — the frontend POSTs the already-built bytes to
   `POST /settings/printer-profiles/{id}/print-network`, and the backend
   (`app/utils/network_print.py`) opens a socket to
   `connection_details.{ip,port}` (default port 9100, the de facto
   ESC/POS "raw"/JetDirect port) and writes them verbatim. Also available
   for dot-matrix (a network print-server fronting the printer).
4. **Bluetooth (`connection=bluetooth`):** reaches a BLE (not Classic/SPP)
   thermal printer directly from the browser via Web Bluetooth GATT
   (`utils/webBluetoothPrinter.ts`) — no server round-trip. Pairing (from
   Settings → Printers) stores `connection_details.
   {bluetooth_device_id,bluetooth_device_name}`; the paired
   `BluetoothDevice` only lives for the page session (Web Bluetooth has no
   reliable persisted-pairing API yet), so a page reload needs a "Re-pair"
   tap. Bytes are written in small chunks with pacing, tuned against real
   BLE thermal-printer hardware, to avoid overrunning the printer's onboard
   buffer.
5. **RawBT (`connection=rawbt`):** hands bytes to the free RawBT Android
   app via an `intent:` URL (`utils/rawbtPrinter.ts`) — RawBT then handles
   the actual USB/Bluetooth/WiFi connection using Android's native stack,
   configured entirely inside the RawBT app itself (nothing to pair on
   StoreMate's side). The most robust option for a WiFi printer reached
   from an Android billing tablet.
6. **Logo rendering:** the company logo is rasterized with Floyd-Steinberg
   dithering (`utils/escpos.ts`), which reads far better than a flat
   threshold for photographic/gradient art on a 1-bit thermal head — the
   same technique used the same way for the equivalent path in KOTMate TN.
   Text (Tamil item-name rasterization) and the UPI QR code deliberately
   stay flat-thresholded instead, since dithering would blur glyph edges
   and can break QR scannability.

This keeps the core app 100% web-based while still supporting the mix of
legacy and modern hardware common in TN retail (a fixed counter thermal
printer, a WiFi printer, a BLE printer, or a cashier's Android tablet).

## Scalability path (documented, not built in v1)
- Shared-schema multi-tenancy can be split to schema-per-tenant or a
  dedicated DB per large chain customer later — repository layer already
  isolates all queries by `tenant_id`, so this is a migration, not a
  rewrite.
- Read replicas can be added in front of reporting queries if a tenant's
  data volume grows large (Pro Max multi-store).
- Stateless FastAPI containers behind Nginx can be horizontally scaled on
  Hostinger VPS/Cloud as needed; session state lives only in JWT + DB.
