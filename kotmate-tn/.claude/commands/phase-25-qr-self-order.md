# /phase-25-qr-self-order

Read `CLAUDE.md` §4, §5, §6, §8, §9, §11 before starting. This is a genuinely new
customer-facing surface, not an extension of an existing phase — it introduces a
second, unauthenticated (guest-token) client alongside the staff app, reusing Phase
07/08/09's order/KOT/bill machinery underneath rather than duplicating it.

## Goal

Let a dine-in customer scan their table's QR code, browse the menu on their own phone
(optional name/phone, never mandatory), order items across multiple rounds — each
round firing a real KOT ticket exactly like a staff-placed order — track ticket status
live, preview their bill, and pay via any UPI app. Billing itself (the actual `bills`
row) and payment confirmation stay staff-only actions, per CLAUDE.md §5's existing
billing RBAC — this phase does not create a self-checkout bypass. Pro Max only
(`plans.features.qr_self_order`), matching the KDS/`pos_operator_role` gating
precedent (CLAUDE.md §6).

Decisions locked for this phase (revisit later, don't relitigate here):
- Guest-placed KOT tickets fire **immediately** — no staff approval step. The
  guardrail is stock, not human review: `available_qty`/`track_inventory` (CLAUDE.md
  §11) must be enforced identically to the staff POS grid — an out-of-stock item is
  unselectable, not just discouraged.
- "I've Paid" only **notifies staff to confirm and finalize at the counter** — it
  never auto-creates a `bills` row. A self-reported UPI payment is not proof of
  payment; a real payment-gateway webhook is a future phase.
- **One QR code per table, one shared cart.** A separate physical QR per seat was
  considered and rejected (production feedback — printing/laminating/replacing a code
  per seating position isn't something a restaurant can realistically maintain).
  Instead a table has exactly one printed QR; everyone who scans it orders into that
  table's single shared order/cart, exactly like a table already works today for
  staff without seat-splitting (CLAUDE.md §11's `party_label`/`CustomerSelectorBar`
  seat-splitting is a separate, staff-side-only feature this phase does not touch or
  reuse — a QR order's `party_label` is always `NULL`). There is nothing to "detect"
  or assign per customer: the table's QR *is* the identity. If a table's guests want
  a split bill, staff still handle that the same way they already do today.

## Scope

### 1. Data model (additive-only — see CLAUDE.md's DB-safety rule)

- `table_qr_codes` (`UUIDPKMixin`, `TimestampMixin`, `tenant_id_column()`):
  `location_id`, `table_id` (FK `tables.id`, **unique** — one row per table),
  `qr_token` (opaque random string, unique, never rotates — a torn/reprinted QR is the
  reset path), `is_active`. `location_id` is stored directly (not just derivable via
  `table_id`) for the same reason `orders.location_id` already is: no location-level
  RLS exists, every query filters explicitly (CLAUDE.md §4). Resolving a `qr_token` is
  therefore a single lookup that hands back tenant/location/table together. Created
  lazily the first time a `tenant_admin` generates that table's QR from Table Master.
- `guest_sessions` (`UUIDPKMixin`, `TimestampMixin`, `tenant_composite_index`):
  `location_id`, `table_id`, `customer_name`/`customer_phone` (both nullable,
  tenant-wide optional info about whoever's currently ordering — not a seat
  identity), `order_id` (nullable until the first item is added), `status` ∈
  `active`/`payment_claimed`/`closed`, `expires_at`. A partial unique index on
  `(tenant_id, table_id) WHERE status='active'` — **at most one active session per
  table** — so any scan of that table's one QR resolves to this same row until staff
  finalizes the bill (which closes it) or it expires.
- `orders.source` (`String`, default `'staff'`, values `staff`/`guest`) — additive
  column, every existing row backfills to `'staff'`, zero behavior change for the
  current app. Drives the small "📱 Self-order" badge on the KOT Tickets
  popup/Kitchen Display.
- `users.is_system_account` (`Boolean`, default `false`) — marks the one synthetic,
  `is_active=false`, un-loginable user per tenant (`user_id` composed as
  `{tenant_code}QRORDER`, same composition rule as any tenant-scoped login per
  CLAUDE.md §5, `role=pos_user`, `incentive_rate=NULL` so it never earns commission)
  created lazily the first time a tenant's first guest order is placed. This is the
  FK target for `orders.pos_user_id`/`bills.pos_user_id` on guest-originated orders —
  deliberately **not** a nullable FK: `bill_service`/`order_service`/`report_service`
  already do unconditional `.scalar_one()` joins against `User` in half a dozen places
  (Phase 07/09/11), and a nullable column would mean touching every one of those call
  sites and every Cashier-wise join. A real (if inert) user row is the smallest-
  blast-radius option. Because it's `is_active=false`, it's automatically excluded
  from Phase 04's seat-cap count and from `GET /api/v1/users`' listing — add an
  explicit `WHERE is_system_account = false` there too so it can never appear in User
  Management even if a future query stops filtering on `is_active`. It intentionally
  **does** appear as its own row in Cashier-wise Sales/Cashier Incentive (Phase 11) —
  a useful "how much revenue is self-service vs. staff-assisted" signal for the
  owner, correctly earning ₹0 incentive since `incentive_rate` is null.
- Migration seeds `plans.features.qr_self_order = true` on the `pro_max` row only
  (data-only migration, same shape as phase-22's `ffa2fb832bd7`).

### 2. Guest auth — a second, narrow token type

- `app/core/security.py`: `create_guest_token(guest_session_id, tenant_id,
  location_id, table_id, expires_delta)` — `type: "guest"` claim (not `"access"`),
  carries **only** `guest_session_id`/`tenant_id`/`location_id`/`table_id`, no
  `role`/`user_id`/customer identity of any kind. `location_id` is required, not
  optional: the guest frontend has no other way to know which location it's ordering
  at, and it needs that value verbatim to open `/ws/location/{location_id}` for live
  KOT status (Phase 08's websocket takes `location_id` as a URL path segment the
  caller must supply, the same way the staff POS screen already does). All of it is
  also returned directly in the session-creation response body (not just buried in
  the JWT) so the frontend never has to decode the token just to get values it needs
  immediately. Reuses the existing `JWT_SECRET`/`_create_token` helper.
- `app/core/deps.py`: new `CurrentGuest` dataclass (`guest_session_id`, `tenant_id`,
  `location_id`, `table_id`) + `get_current_guest(credentials)` dependency, parallel
  to `CurrentUser`/`get_current_user` but rejecting any token whose `type != "guest"`.
  Guest routes depend on this, never on `get_current_user` — the two auth worlds
  don't mix, so a leaked/expired staff token can never be replayed against a guest
  route or vice versa.
- `POST /api/v1/guest/sessions/{qr_token}` (no auth — this *is* the login): one
  lookup — `qr_token → table_qr_codes` — hands back `tenant_id`/`location_id`/
  `table_id`. Upserts the `active` `guest_sessions` row for that table — creating it
  on a fresh scan, resuming it unchanged on any subsequent scan of the same table's
  QR by anyone (that's the whole "shared cart" mechanic, not a special case) — and
  returns the guest JWT. Optional `PATCH /api/v1/guest/sessions/me` to set name/phone
  after the fact — never a precondition to ordering.
- Every other `/api/v1/guest/*` route depends on `get_current_guest` and re-derives
  `tenant_id`/`location_id`/`table_id` from the token, exactly the way staff routes
  never trust a client-supplied tenant id.

### 3. Guest ordering — thin wrapper over Phase 07/08, not a parallel implementation

- `GET /api/v1/guest/menu` — same shape as the staff `listPosItems`/`listPosSections`
  pair, filtered to the guest's own table's section/location. Item cards must carry
  the same `available_qty`/`track_inventory` fields the staff `ItemCard.tsx` already
  reads, since the guest-facing grid reuses that exact out-of-stock/low-stock gating,
  not a re-derived copy of it.
- `GET /api/v1/guest/cart` — rehydrates whatever's already in the table's shared
  order (or `null` if nothing's been added yet), so any phone that joins an
  in-progress table sees the current cart immediately, and a reload/backgrounded tab
  never loses sight of it.
- `POST /api/v1/guest/cart` — thin wrapper calling the existing
  `order_service.create_order`/`apply_order_update`, with the guest session's
  `order_id` created against the synthetic system user (`pos_user_id`),
  `waiter_id=None`, `party_label=None` (this is deliberately the same "no split"
  default path a staff-placed order without seat-splitting already uses). Sets
  `guest_sessions.order_id` on first call.
- `POST /api/v1/guest/send-kot` — calls `kot_service.send_kot(session, tenant,
  order_id)` directly (it already takes no `current_user`, CLAUDE.md's existing
  repeat-KOT/stock-deduction logic applies unchanged). A guest can call this
  repeatedly across multiple ordering rounds exactly like a cashier tapping "Add to
  KOT" again — no new mechanic.
- `GET /api/v1/guest/order-status` — polls `kot_service.list_active_tickets` filtered
  to the table's own `order_id`, or connects to the existing
  `/ws/location/{location_id}` socket read-only (the guest client only ever reads
  `kot_ticket` messages matching its own `order_id`, never the full location fan-out
  a staff screen relies on — enforce this filter client-side since the manager itself
  is a per-location broadcast, not per-order).
- **Staff visibility is non-negotiable**: no filter anywhere hides `source='guest'`
  orders from the existing KOT Tickets popup, Kitchen Display, or table-occupied
  badge — they must look and behave exactly like any dine-in order to staff, just
  carrying the small badge from §1.

### 4. Bill preview + payment handoff (billing RBAC untouched)

- `GET /api/v1/guest/bill-preview` — computes the same subtotal/CGST/SGST/discount/
  round-off a real `POST /bills` would (reuses `bill_service.preview_bill` directly),
  returns it read-only. No `bills` row is created here.
- `POST /api/v1/guest/request-bill` — flips `guest_sessions.status` to
  `payment_claimed` and broadcasts a `payment_claimed` message over the existing
  location websocket (same channel Kitchen Display/POS already listen to) so a
  cashier sees a prompt to go finalize that table's bill. This is the entire "payment"
  surface on the backend for this phase — finalizing still only ever happens via the
  existing `POST /bills`, `require_role("tenant_admin", "pos_user", "pos_operator")`
  gate untouched.
- Guest UI's "Pay via UPI" button is a plain `upi://pay?pa=...&pn=...&am=...` deep
  link (same construction as `bill_service`'s existing bill-print QR payload) rendered
  as a tappable button, **not** a QR image — the guest is already on the paying
  device, so a scannable code here would be asking them to scan their own screen.
  Generic "UPI" framing only (CLAUDE.md §9 — no app-specific branding).
- `guest_sessions.status='closed'` once staff finalizes the bill for that order (hook
  into `bill_service.finalize_bill`, right where it sets `order.status = "billed"`,
  to also close any `guest_sessions` row pointing at that order) — the table's one
  QR is then a clean slate: the next scan starts a brand-new shared session.

### 5. Settings + QR provisioning

- New Settings toggle (`tenant_admin`, visible only when
  `meData.features?.qr_self_order === true`, same visibility pattern as Phase 22's
  Stock toggle): `tenants.qr_self_order_enabled` (default `false` — same
  additive-toggle shape as `waiter_mandatory_enabled` from Phase 24) lets a Pro Max
  tenant have the feature available but not yet turned on for the floor.
- Table Master gains a **per-table "QR Code" action** (`tenant_admin`) — no location
  dropdown or "select a location first" step anywhere in this screen, since a table
  already belongs to exactly one location and that's all QR generation needs.
  Generates (idempotently — a table only ever gets one code, calling again just
  returns the existing one) a single `table_qr_codes` row and shows its scan link for
  the admin to print/laminate once and leave on the table.
- `/auth/me` gains `qr_self_order_enabled` (effective flag: plan feature AND tenant
  toggle, same computed-flag convention as `stock_tracking_enabled`).

### 6. Frontend — a second, separate client, not a mode of the POS app

- New route `/order/:qrToken` mounted outside the existing authenticated shell
  entirely — no sidebar, no login page, no `ProtectedRoute`. A single component owns
  simple internal tab state (Menu / Status / Bill) rather than deep-linkable
  sub-routes, since a guest never needs to bookmark a specific screen mid-order.
  Guest JWT stored the same way the staff app stores tokens (`localStorage`), via a
  **separate** key so a guest session on a shared/kiosk device can never collide with
  or be read as a staff session, and this axios instance's 401 handling never touches
  the staff auth store or redirects to `/login` (a guest's session expiring must never
  be able to log a staff member out on a shared device).
- Reuses `ItemCard.tsx`'s stock-badge/out-of-stock visuals and Indian-number-formatting
  helpers (`formatINR`) as-is; does **not** reuse `CartPanel.tsx`/`TableWaiterBar.tsx`
  wholesale (those assume a logged-in staff role and hotkeys) — a new, minimal cart
  sheet/status list/bill view built for one-handed phone use, same network-tolerant
  "Saving…/Saved" indicator CLAUDE.md §9 already requires for the waiter's mobile flow
  (guests are on the same patchy restaurant Wi-Fi).
- Staff side: `KotTicketsPopup.tsx`/Kitchen Display gain the "📱 Self-order" badge
  (§1); the POS grid's existing websocket connection (already open for stock
  overrides) also surfaces a toast on `payment_claimed` so a cashier is actively
  notified rather than needing to notice a status change — one shared connection,
  not a second websocket just for this.

## Acceptance Criteria

- Scanning a table's QR with no existing active session creates one and lands on the
  menu with no login/signup screen of any kind; name/phone are always skippable;
  neither the guest nor staff ever has to pick a location or a customer identity
  anywhere in the flow — everything comes from which table's QR was scanned.
- A second phone scanning the same table's QR while an order is in progress sees and
  can add to that exact same shared cart — verified by both phones' `GET
  /guest/cart` returning the same order id and item list.
- Adding an out-of-stock (`available_qty=0`, `track_inventory=true`) item is
  impossible from the guest menu, identical to the staff POS grid's own gating.
- Each "Send to Kitchen" tap fires a real KOT ticket, decrements stock exactly like a
  staff-placed order, and appears on the Kitchen Display / KOT Tickets popup
  indistinguishable in every way except the "📱 Self-order" badge; a second round
  after the first ticket already fired correctly uses the existing repeat-KOT append
  behavior (CLAUDE.md §11), never merging into the already-sent line.
- Guest order-status view reflects a ticket's New → Preparing → Ready transitions
  live, sourced from the same data the Kitchen Display uses.
- For a tenant with multiple locations: a guest's JWT/session carries the correct
  `location_id` for the table they actually scanned, their websocket connects to that
  location's own `/ws/location/{location_id}` channel, and their order/KOT ticket
  never appears on a different location's Kitchen Display or KOT Tickets popup — a
  QR code printed for a Branch Two table must never resolve to or affect Main branch
  data.
- "Request Bill" never creates a `bills` row and never lets the guest set the order to
  `billed` — only staff calling the existing `POST /bills` does that; a guest token
  calling `POST /bills` directly is rejected (invalid token type for that route's
  dependency).
- Tapping "Pay via UPI" opens the guest's own UPI app pre-filled with the correct
  amount; no QR image is shown to the guest.
- The synthetic per-tenant system account never appears in `GET /api/v1/users`, never
  counts against the plan's seat cap, and never accrues incentive — but its bills do
  show up as their own row in Cashier-wise Sales/Incentive with ₹0 incentive.
- Once staff finalizes the bill for a table's QR order, the very next scan of that
  same table's QR starts a brand-new session with no cart — never resumes the
  just-billed one.
- Turning the tenant's QR toggle off immediately rejects any in-flight guest
  session's next request with a clear "ordering is currently unavailable" message,
  without deleting `table_qr_codes` rows (same soft-disable convention as every other
  tenant toggle in this codebase).
- Lite/Pro tenants: no QR action in Table Master, `/auth/me`'s
  `qr_self_order_enabled` is always `false`, and every `/api/v1/guest/*` route 403s
  regardless of a valid-looking guest token, since the plan-feature check happens
  before the token is even trusted for anything beyond identifying the tenant.
