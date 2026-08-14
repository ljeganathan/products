# API Contracts — StoreMate TN

Living document. Every phase that adds/changes endpoints MUST update this
file. Base URL: `/api/v1`. Auth: `Authorization: Bearer <JWT>` unless noted
public. All list endpoints support `?page=&page_size=&search=`.

## Auth (Phase 2)
- `POST /auth/login` — public. `{email, password}` → `{access_token, refresh_token, user}`.
  `product_owner` accounts have no `tenant_id`; their access token carries
  `tenant_id: null` and `role: product_owner`.
- `POST /auth/refresh` — public. `{refresh_token}` → `{access_token}`
- `POST /auth/logout` — 204. Stateless JWT (no refresh-token/session store in
  this schema); the client discards both tokens. Requires a valid access token.
- `GET /auth/me` — returns the caller's own user record.

Access tokens embed `{user_id (sub), tenant_id, store_id, role, type: "access",
iat, exp}`; refresh tokens embed `{user_id (sub), type: "refresh", iat, exp}`.
Both are signed HS256 JWTs (`core/security.py`). A missing/invalid/expired
token, or one presented with the wrong `type` for the endpoint, returns 401.

## Platform / Product Owner (Phase 7)
All endpoints below are `product_owner` only unless noted. A tenant's
`usage` block (`users_count/limit`, `stores_count/limit`,
`printer_profiles_count/limit`) is computed live from `subscription_service.
get_tenant_usage` on every read — `*_limit: -1` means unlimited.
- `GET /platform/tenants` — paginated, `?search=&status=`.
- `POST /platform/tenants` — `{name, owner_email, owner_phone, plan_code,
  store_name?, admin_name, admin_email, admin_password}`. Creates the
  tenant, its default store, an active subscription on the given plan, and
  its first admin user in one transaction. 409 if `owner_email` or
  `admin_email` is already taken.
- `GET /platform/tenants/{id}`
- `PATCH /platform/tenants/{id}` — `{status}` (`trial|active|suspended|
  cancelled`). Suspending/cancelling takes effect on that tenant's *next*
  login or token refresh (`auth_service._check_tenant_active`) — an
  already-issued access token still works until its 30-min expiry, since
  there's no session store to revoke it early (CLAUDE.md's "no Redis"
  constraint).
- `GET/POST/PATCH /platform/plans` — edits the `plans` table directly
  (price, limits, `features_json`) with no code deploy, per CLAUDE.md §4.
  A change is picked up immediately by every tenant on that plan, since
  `plan_limits` re-reads it fresh on every request.
- `GET /platform/subscriptions` — paginated, `?tenant_id=&status=`.
- `POST /platform/subscriptions` — `{tenant_id, plan_id}`. Cancels any
  existing active subscription for that tenant first (used for manual
  recovery; tenant creation goes through `POST /platform/tenants` instead).
- `PATCH /platform/subscriptions/{id}` — `{extra_users?, extra_stores?}`
  add-ons (₹99/user, ₹999/store per `docs/SUBSCRIPTION_TIERS.md`).
- `PATCH /platform/subscriptions/{id}/change-plan` — `{plan_id}`. 409 with a
  specific reason per over-limit resource (users/stores/printer profiles)
  if the tenant's current usage exceeds the target plan — nothing is
  changed until every reason clears. On success, also clears any pending
  tenant-side upgrade request (see `/settings/subscription` below).
- `GET /platform/invoices` — paginated, `?tenant_id=&status=`.
- `POST /platform/invoices/generate` — `{subscription_id}`. Creates a
  `pending` invoice for the period starting at the subscription's current
  `current_period_end` (amount = plan price + extra-user/store add-ons +
  18% GST); does not itself change the subscription's period.
- `PATCH /platform/invoices/{id}` — `{status}`, one of `paid|failed|void`.
  `paid` rolls the subscription's billing period forward by 30 days and
  sets its status back to `active`. `failed` sets the subscription to
  `past_due` — there is no dedicated "overdue" invoice status, so the
  console's "mark overdue" action maps to `failed`.
- `GET/PATCH /platform/settings` — `{maintenance_mode, maintenance_message}`,
  a singleton row created lazily on first read.
- `GET /platform/maintenance-status` — any authenticated role (not just
  product_owner). What the app shell polls on load to show/hide the
  maintenance banner; the frontend hides the banner for `product_owner`
  itself since a maintenance window never applies to the console.

## Tenant-side Subscription (Phase 7)
`admin` only.
- `GET /settings/subscription` — the caller's own tenant's plan, billing
  period, live usage vs limits, and any pending upgrade request.
- `GET /settings/subscription/available-plans` — `{id, code, name,
  price_paise}` for every active plan, so the upgrade-request UI can offer a
  plan to switch to without exposing the full `/platform/plans` detail
  (limits, `features_json`) that's console-only.
- `POST /settings/subscription/upgrade-request` — `{plan_id}`. Manual-payment
  v1 has no self-serve checkout: this just records
  `subscriptions.requested_plan_id/upgrade_requested_at` for the product
  owner console to see and act on via `change-plan` above.

## Users (Phase 2/6)
- `GET /users` — paginated (`?page=&page_size=&search=`), `admin` only, scoped
  to the caller's tenant.
- `POST /users` — `admin` only. Creates an `admin` or `pos_user` within the
  caller's tenant (cannot create `product_owner`). Enforces `plans.max_users`
  (+ `subscriptions.extra_users`) via `middleware/plan_limits.check_user_limit`
  — returns 402 with a clear message if the plan's user limit is reached.
- `GET/PATCH /users/{id}` — `admin` only, scoped to the caller's tenant; a
  user id belonging to another tenant returns 404 (tenant isolation).
- `DELETE /users/{id}` — `admin` only; soft-deletes by setting `is_active =
  false` (matches CLAUDE.md §5's "deactivate", not a hard delete).

## Categories & Items (Phase 3)
Read endpoints (`GET`) are `admin` + `pos_user` (view-only per CLAUDE.md §5);
writes are `admin` only.
- `GET/POST /categories` — paginated, `?search=`. Deleting a category that is
  still referenced by an item or sub-category returns 409.
- `GET/PATCH/DELETE /categories/{id}`
- `GET/POST /items` (paginated, `?search=&category_id=&store_id=`).
  `?barcode=` bypasses pagination/search and does a single indexed
  `(tenant_id, barcode)` lookup, returned in the same paginated envelope
  (0 or 1 item) for a consistent response shape.
- `GET/PATCH /items/{id}`; `DELETE /items/{id}` soft-deactivates
  (`is_active = false`), matching the `users` pattern — items are referenced
  by `stock`/`bill_items`, so a hard delete isn't safe.
- `POST /items/bulk-import` — multipart CSV upload, `?store_id=` (falls back
  to the caller's default store). Template columns: `name_en, name_ta,
  category, brand, pack_size, barcode, sku, unit, mrp, selling_price,
  cost_price, tax_profile, hsn_code, reorder_level, reorder_qty,
  opening_stock`. `category`/`tax_profile` are matched by name (case
  insensitive) against the tenant's existing records — they are not
  created on the fly. Bad rows are skipped and reported individually
  (`{total_rows, created_count, error_count, errors: [{row_number, errors[]}]}`)
  rather than failing the whole import. `opening_stock > 0` creates the
  item's initial `stock` row.
- Items requiring a `store_id` (create, bulk-import) default to the caller's
  token `store_id`; a multi-store admin (Pro Max) with no default store must
  pass one explicitly, or gets a 400.

## Stock (Phase 3/6)
Read endpoints are `admin` + `pos_user`; `POST /stock/adjust` is `admin` only
(POS billing will decrement stock via the bill service in Phase 5, not this
manual-adjustment endpoint).
- `GET /stock` — paginated, joins `items` for name/barcode/reorder_level,
  computes `low_stock = quantity_on_hand <= reorder_level`.
- `POST /stock/adjust` — `{item_id, store_id?, change_qty, reason,
  reference_id?}`. Writes `stock` and a `stock_movements` row in the same
  transaction (single `db.commit()`), so they're atomic. Rejects if the
  resulting quantity would go below 0 (400).
- `GET /stock/movements` — paginated, `?item_id=`.
- `GET /stock/low-stock` — gated by `feature_enabled(tenant_id,
  "low_stock_alerts")`; 403 with an upgrade message on Lite, 200 on
  Pro/Pro Max.

## Tax & Settings (Phase 3/6)
Writes are `admin` only. `GET /settings/tax-profiles` and `GET
/settings/printer-profiles` are also readable by `pos_user` (Phase 5
addition) — the POS cart preview needs tax rates to compute totals, and
print dispatch needs to know which profile to send a receipt to; this
mirrors the Stock/Item/Category "view-only" pattern in CLAUDE.md §5, which
predates POS existing but is the same underlying need. Company settings
remain fully `admin`-only (no billing-time read need).
- `GET/POST/PATCH/DELETE /settings/tax-profiles` — `cgst_pct/sgst_pct` or
  `igst_pct` are validated against the standard TN FMCG slabs (0/5/12/18/28%)
  but never hard-rejected; a mismatch is returned as a `warning` string in
  the response so exempt/custom rates stay usable. Setting `is_default:
  true` on one profile automatically unsets it on all other profiles for
  that tenant. Deleting a profile still referenced by an item returns 409.
  A profile's `igst_pct` is stored alongside `cgst_pct`/`sgst_pct` as the
  equivalent inter-state rate for future invoicing — it does not mark the
  profile inter-state-only; billing (Phase 5) always charges cgst+sgst.
- `GET/PATCH /settings/company` (`?store_id=`, defaults to the caller's
  store) — lazily creates a `company_settings` row from the `stores` record
  on first access if one doesn't exist yet (also used by
  `services/billing_service.build_print_payload` so a store's very first
  sale can still print before anyone visits Settings).
- `POST /settings/company/logo` — multipart upload (PNG/JPEG/WEBP, ≤5MB by
  default `MAX_LOGO_UPLOAD_MB`), saved under `MEDIA_ROOT/logos/<tenant_id>/
  <store_id>.<ext>` and served from `/media/...` (see `docker-compose.yml`'s
  `media_data` volume). Swapping to S3-compatible storage later only
  touches `services/media_service.py` — callers only ever see the returned
  `logo_url`.
- `GET/POST/PATCH/DELETE /settings/printer-profiles` (`?store_id=`) — gated
  by `check_printer_profile_limit` (Phase 2). `is_default: true` unsets any
  other default profile for that store. `connection` accepts
  `webusb|local_agent|network|wifi|bluetooth|rawbt`; `connection_details`
  is a free-form JSON object whose shape depends on `connection` (see
  `docs/DATABASE_SCHEMA.md`) — the frontend print dispatcher
  (`features/pos/printDispatch.ts`) is the only reader.
- `POST /settings/printer-profiles/{id}/print-network` — `{data_base64}`,
  204 on success. Only valid for `network`/`wifi` profiles (400 otherwise).
  Browsers can't open a raw TCP socket, so network/WiFi printers are the one
  connection type dispatched server-side: the frontend builds the same
  ESC/POS (or dot-matrix text) bytes it would send WebUSB/local-agent, then
  hands them here and the backend opens the socket
  (`app/utils/network_print.py`, raw port 9100 by default). Returns 502 with
  a cashier-safe message on an unreachable printer.
- `GET/PATCH /settings/language` — `{language_pref: "en"|"ta"}`. CLAUDE.md §7
  frames this as a per-tenant setting, but the schema has no tenant-level
  language column (`docs/DATABASE_SCHEMA.md`) — only `users.language_pref`.
  This operates on the calling admin's own `language_pref`, which is what
  actually drives the UI language at login (Phase 4) — the practical stand-in
  for a "store default" without a schema change.

## POS / Billing (Phase 5)
All endpoints below are `admin` + `pos_user`. A `pos_user` is restricted to
their own shift's bills everywhere (`cashier_id` is forced to their own
user id, ignoring any `cashier_id` filter); fetching another cashier's bill
by id returns 404 (not 403) to match the tenant-isolation pattern.
- `GET /pos/items/search?q=&store_id=&limit=` — fast active-item name/SKU/
  barcode search, the fallback once the client-side item cache (TanStack
  Query, refreshed every 5 min) doesn't have a local match.
- `POST /bills` — creates a bill. Body: `{store_id?, customer_name?,
  customer_phone?, payment_mode, items: [{item_id, qty, discount_type?,
  discount_value?}], bill_discount_type?, bill_discount_value?, hold?}`.
  `discount_value` is paise for `flat`, basis points for `percent` (matches
  `discount_rules.value`). The server recomputes every total from live
  `items`/`tax_profiles` data (`services/billing_service.compute_bill_totals`)
  — client-sent prices/totals are never trusted. `hold: true` creates the
  bill with `status=held` and does **not** touch stock; `hold: false`
  (default) decrements stock per line and fires a background low-stock
  check. Bill numbers are sequential per store (`MAX(bill_number)+1`); a
  same-instant collision returns 409 asking the client to retry — there is
  no dedicated counter table.
- `POST /bills/{id}/resume` — only valid on a `status=held` bill. Fetches
  its `bill_items`, **deletes** the held bill + items, and returns
  `{store_id, customer_name, customer_phone, payment_mode, items}` for the
  client to reload into an editable cart. A fresh `POST /bills` call
  finalizes it under a new bill number. Per-line/bill discounts are **not**
  reconstructed (only the combined post-discount amount is stored on
  `bill_items`, not the original discount input) — the cashier re-applies
  them if still wanted.
- `GET /bills` — saved bill search: `?page=&page_size=&store_id=
  &bill_number=&date_from=&date_to=&cashier_id=&customer_phone=&status=`.
  Response adds `{saved_bill_days, window_start, requested_from_clamped}` —
  `saved_bill_days` come from the plan (Lite=7, Pro=90, Pro Max=-1
  unlimited); results are always silently clamped to that window server-side
  (a Lite tenant can never see bills older than 7 days regardless of the
  query), and `requested_from_clamped=true` specifically flags when the
  caller's own `date_from` asked for something outside that window, so the
  frontend can show an upgrade CTA.
- `GET /bills/{id}` — full detail including `items`.
- `POST /bills/{id}/print` — builds `BillPrintPayload` (company header incl.
  logo/GSTIN/footer, line items, tax breakdown, cashier name) from live
  data and increments `printed_count`. The actual ESC/POS or plain-text
  byte layout is built client-side (`frontend/src/utils/escpos.ts` /
  `dotmatrix.ts`) from this payload — the backend never generates print
  bytes.
- `POST /bills/{id}/cancel` — `held` → deleted with no stock impact (stock
  was never decremented); `completed` → stock is reversed per line
  (`stock_movements` reason=`return`) and status becomes `cancelled`.
  Cancelling an already-cancelled bill returns 400.

## Discounts (Phase 6, Pro+)
`admin` only, all methods gated by `feature_enabled(tenant_id,
"discount_rules_advanced")` (Pro/Pro Max) — 403 with an upgrade message on
Lite, matching the `low_stock_alerts` gating pattern from Phase 3.
- `GET /discount-rules` — paginated, `?scope=item|category|bill&is_active=`.
- `POST /discount-rules` — `{scope, target_id?, type, value, starts_at?,
  ends_at?, is_active}`. `target_id` (an `item.id` or `category.id`) is
  required when `scope` is `item`/`category` and must be omitted when
  `scope=bill` (422 otherwise). `value` uses the same paise/basis-points
  convention as everywhere else.
- `PATCH/DELETE /discount-rules/{id}`

Note: these rules are defined here but not yet *applied* automatically at
checkout — Phase 5's POS bill/line discounts are cashier-entered per sale.
Wiring discount_rules into automatic checkout application is a later-phase
enhancement.

## Dashboard (Phase 8)
`admin` only. All endpoints scope to `?store_id=` when given, else the
caller's own default store, else (multi-store admin with no default store)
every store the tenant has — that "no store_id, no default store" case is
the Pro Max consolidated view, not an error (unlike the item/stock/settings
`resolve_store_id` pattern from earlier phases, which 400s in that case).
- `GET /dashboard/summary?store_id=` — always available. Today's sales
  total, bill count, average bill value, top 5 items by revenue, and
  low-stock count (always `0` if `low_stock_alerts` is off on Lite — not an
  error, per CLAUDE.md's plan-gating philosophy).
- `GET /dashboard/trend?date_from=&date_to=&group_by=day|hour&store_id=` —
  gated by `feature_enabled(tenant_id, "dashboard_range")` (Pro/Pro Max);
  403 with an upgrade message on Lite.
- `GET /dashboard/breakdown?by=category|cashier|payment_mode&date_from=&date_to=&store_id=`
  — same `dashboard_range` gate. `category` is attributed at the line-item
  level (`bill_items.line_total_paise`); `cashier`/`payment_mode` at the
  bill level (`bills.total_paise`) — a bill spanning categories would
  double-count if category breakdown summed the bill total instead.
- `GET /dashboard/stores?date_from=&date_to=` — gated by
  `feature_enabled(tenant_id, "multi_store")` (Pro Max only). Per-store
  totals for every store in the tenant (LEFT JOIN, so a store with zero
  bills in range still appears with `0`, not omitted).
- `GET /dashboard/export.pdf?date_from=&date_to=` — same `multi_store` gate.
  Renders today's summary + the store-totals range as a PDF via `reportlab`
  (`services/dashboard_export_service.py`) — a deliberate substitute for the
  phase brief's suggested `weasyprint`, which needs Cairo/Pango/GDK-Pixbuf
  system libraries `backend/Dockerfile` doesn't install; reportlab is
  pure-Python-installable and draws the same KPI/table content directly.
- `GET /platform/dashboard` — product_owner only. `{active_tenant_count,
  trialing_count, churned_this_month_count, mrr_paise, plan_mix: [{plan_code,
  plan_name, tenant_count}], overdue_invoices_count}`. MRR sums
  `plan.price_paise + extra_users×₹99 + extra_stores×₹999` (Phase 7's
  add-on pricing) over every `ACTIVE` subscription. `churned_this_month_count`
  uses `tenants.updated_at` as a proxy for "when cancelled" — there's no
  dedicated `cancelled_at` column. `overdue_invoices_count` counts
  `subscription_invoices.status = failed`, matching Phase 7's established
  "mark overdue" → `failed` mapping (there's no separate `overdue` enum
  value).

## Notifications (Phase 6/8, topbar bell + low-stock digest)
`admin` only (same audience as the Store Dashboard row in CLAUDE.md §5).
- `GET /notifications` — paginated, `?store_id=&is_read=`. A row with
  `created_for_user_id: null` is visible to every admin of its store; one
  with a specific user id is visible only to that user. `reference_id`
  (Phase 8) is an `items.id` for `type=low_stock` — the frontend's
  click-through target.
- `PATCH /notifications/{id}/read` — marks a single notification read.
- Two things create `low_stock` notifications, both deduped against the
  same `LOW_STOCK_COOLDOWN_HOURS` (24h) window per `(tenant_id, store_id,
  reference_id)` so a slow-moving low-stock item doesn't spam a
  notification per sale or per scan:
  - `services/notification_service.check_and_notify_low_stock` — a
    `BackgroundTask` fired once per line item after a completed sale
    (Phase 5).
  - `services/notification_service.run_low_stock_scan` — an APScheduler job
    every 15 minutes (`core/scheduler.py`), scanning every tenant with
    `low_stock_alerts` on for items sitting at/under `reorder_level`
    regardless of whether anyone's sold them recently (e.g. after a manual
    stock adjustment or a lowered reorder level).

## Reports (Phase 8)
`admin` + `pos_user` (a `pos_user` is forced to their own `cashier_id`,
same restriction pattern as `GET /bills`). Reuses the `dashboard_range`
feature flag from the Dashboard section above — `docs/SUBSCRIPTION_TIERS.md`
bundles "date-range sales, GST summary, CSV export" as one Pro+ capability,
not three separate flags.
- `GET /reports/sales?date_from=&date_to=&store_id=&cashier_id=` — total,
  bill count, average bill value, and a daily breakdown. On Lite, the
  requested range is silently clamped to today (`range_clamped: true` in
  the response) rather than rejected — mirrors `GET /bills`'s
  `saved_bill_days` clamp pattern (Phase 5).
- `GET /reports/gst-summary?date_from=&date_to=&store_id=&cashier_id=` —
  `{subtotal_paise, discount_paise, cgst_paise, sgst_paise, total_paise,
  bill_count}` summed from the already-persisted `bills` columns (never
  recomputed) over the range. Same Lite clamp behavior.
- `GET /reports/sales.csv?date_from=&date_to=&store_id=&cashier_id=` — 403
  with an upgrade message on Lite (no clamp/fallback — CSV export is
  simply unavailable, per the phase brief). One row per bill; money columns
  are plain decimal strings (`"799.00"`, no ₹ symbol) for spreadsheet/
  accounting-software compatibility.

## Scheduled email digest (Phase 8, Pro Max only)
`core/scheduler.py` runs a daily APScheduler job (08:00 server time) that
emails every tenant's admin(s) a plain-text dashboard-style summary (today's
sales, bill count, low-stock count) via `services/email_service.py`. Gated
by the same `multi_store` flag as the PDF export and store-switcher (Pro Max
only, per `docs/SUBSCRIPTION_TIERS.md`'s "Scheduled email reports" line).
`EmailService` is a real, working `smtplib`-based implementation — unlike
Phase 7's payment gateway (which genuinely can't be implemented without a
paid third-party account), plain SMTP is usable today via a local dev debug
server or a real relay; when `SMTP_HOST` is unconfigured it logs and skips
per recipient rather than pretending to send.

> Each endpoint's exact request/response schema lives in
> `backend/app/schemas/` — this file tracks the surface area and phase of
> origin, not full payload detail.
