# /phase-25-qr-self-order

Read `CLAUDE.md` §4, §5, §6, §8, §9, §11 before starting. This is a genuinely new
customer-facing surface, not an extension of an existing phase — it introduces a
second, unauthenticated (guest-token) client alongside the staff app, reusing Phase
07/08/09's order/KOT/bill machinery underneath rather than duplicating it.

## Goal

Let a dine-in customer scan a QR code on their table, browse the menu on their own
phone (optional name/phone, never mandatory), order items across multiple rounds —
each round firing a real KOT ticket exactly like a staff-placed order — track ticket
status live, preview their bill, and pay via any UPI app. Billing itself (the actual
`bills` row) and payment confirmation stay staff-only actions, per CLAUDE.md §5's
existing billing RBAC — this phase does not create a self-checkout bypass. Pro Max
only (`plans.features.qr_self_order`), matching the KDS/`pos_operator_role` gating
precedent (CLAUDE.md §6).

Decisions locked for this phase (revisit later, don't relitigate here):
- Guest-placed KOT tickets fire **immediately** — no staff approval step. The
  guardrail is stock, not human review: `available_qty`/`track_inventory` (CLAUDE.md
  §11) must be enforced identically to the staff POS grid — an out-of-stock item is
  unselectable, not just discouraged.
- "I've Paid" only **notifies staff to confirm and finalize at the counter** — it
  never auto-creates a `bills` row. A self-reported UPI payment is not proof of
  payment; a real payment-gateway webhook is a future phase.
- One shared cart per table-party (reuses the existing `party_label` seat-splitting
  model, CLAUDE.md §11) — a second phone scanning the same table's QR joins the same
  live order rather than starting a competing one, matching how a table already works
  for staff-placed orders.

## Scope

### 1. Data model (additive-only — see CLAUDE.md's DB-safety rule)

- `table_qr_codes` (`UUIDPKMixin`, `TimestampMixin`, `tenant_id_column()`): `location_id`,
  `table_id` (FK `tables.id`, unique), `qr_token` (opaque random string, unique,
  never rotates — a torn/reprinted QR is the reset path), `is_active`. One row per
  physical table, created lazily the first time a `tenant_admin` prints that table's
  QR from Settings.
- `guest_sessions` (`UUIDPKMixin`, `TimestampMixin`, `tenant_composite_index`):
  `location_id`, `table_id`, `party_label` (same "Customer-1"/"Customer-2" values
  Phase 19 already uses), `customer_name`/`customer_phone` (both nullable), `order_id`
  (nullable until the first item is added), `status` ∈
  `active`/`payment_claimed`/`closed`, `expires_at`. `location_id` is stored directly
  rather than left derivable through `table_id` — every location-scoped staff query in
  this codebase (`orders.location_id` itself included) does the same, since there's no
  location-level RLS, only explicit app-level filtering (CLAUDE.md §4), and a future
  staff-facing "active guest sessions" list needs to filter by the currently-selected
  location the same way `pos-open-orders`/`pos-tables` already do. A partial unique
  index on `(tenant_id, table_id, party_label) WHERE status='active'` — same guard
  shape as `orders`' own party-label index — so a second phone resolves to the
  existing session instead of forking a duplicate cart.
- `orders.source` (`String`, default `'staff'`, values `staff`/`guest`) — additive
  column, every existing row backfills to `'staff'`, zero behavior change for the
  current app. Drives the small "📱 Self-order" badge on the KOT Tickets
  popup/Kitchen Display and the "Self-Order (QR)" label wherever a bill's origin needs
  to read clearly to staff.
- `users.is_system_account` (`Boolean`, default `false`) — marks the one synthetic,
  `is_active=false`, un-loginable user per tenant (`user_id` composed as
  `{tenant_code}QRORDER`, same composition rule as any tenant-scoped login per
  CLAUDE.md §5, `role=pos_user`, `incentive_rate=NULL` so it never earns commission)
  created lazily the first time a tenant's first guest order is placed. This is the
  FK target for `orders.pos_user_id`/`bills.pos_user_id` on guest-originated orders —
  deliberately **not** a nullable FK: `bill_service`/`order_service`/`report_service`
  already do unconditional `.scalar_one()` joins against `User` in half a dozen places
  (Phase 07/09/11), and a nullable column would mean touching every one of those
  call sites and every Cashier-wise join. A real (if inert) user row is the smallest-
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

- `app/core/security.py`: `create_guest_token(guest_session_id, tenant_id, location_id,
  table_id, expires_delta)` — `type: "guest"` claim (not `"access"`), carries **only**
  `guest_session_id`/`tenant_id`/`location_id`/`table_id`, no `role`/`user_id`. The
  `location_id` claim is required, not optional: the guest frontend has no other way
  to know which location it's ordering at, and it needs that value verbatim to open
  `/ws/location/{location_id}` for live KOT status (Phase 08's websocket takes
  `location_id` as a URL path segment the caller must supply, the same way the staff
  POS screen already does). Also returned directly in the session-creation response
  body (not just buried in the JWT) so the frontend never has to decode the token
  just to get a value it needs immediately for its first websocket connect. Reuses
  the existing `JWT_SECRET`/`_create_token` helper.
- `app/core/deps.py`: new `CurrentGuest` dataclass (`guest_session_id`, `tenant_id`,
  `location_id`, `table_id`) + `get_current_guest(credentials)` dependency, parallel
  to `CurrentUser`/`get_current_user` but rejecting any token
  whose `type != "guest"`. Guest routes depend on this, never on `get_current_user` —
  the two auth worlds don't mix, so a leaked/expired staff token can never be replayed
  against a guest route or vice versa.
- `POST /api/v1/guest/sessions/{qr_token}` (no auth — this *is* the login): resolves
  `qr_token → table_qr_codes → table`, upserts the `active` `guest_sessions` row for
  `party_label="Customer-1"` (first scan) or the table's current active session
  (subsequent scans of the same table), returns the guest JWT. Optional
  `PATCH /api/v1/guest/sessions/me` to set name/phone after the fact — never a
  precondition to ordering.
- Every other `/api/v1/guest/*` route depends on `get_current_guest` and re-derives
  `tenant_id`/`table_id` from the token, exactly the way staff routes never trust a
  client-supplied tenant id.

### 3. Guest ordering — thin wrapper over Phase 07/08, not a parallel implementation

- `GET /api/v1/guest/menu` — same shape as the staff `listPosItems`/`listPosSections`
  pair, filtered to the guest's own table's section/location. Item cards must carry
  the same `available_qty`/`track_inventory` fields the staff `ItemCard.tsx` already
  reads, since the guest-facing grid reuses that exact out-of-stock/low-stock gating,
  not a re-derived copy of it.
- `POST /api/v1/guest/cart` — thin wrapper calling the existing
  `order_service.create_order`/`compute_updated_lines`/`apply_line_changes`, with the
  guest session's `order_id` created against the synthetic system user
  (`pos_user_id`) and `waiter_id=None` (no waiter involved). Sets
  `guest_sessions.order_id` on first call.
- `POST /api/v1/guest/send-kot` — calls `kot_service.send_kot(session, tenant,
  order_id)` directly (it already takes no `current_user`, CLAUDE.md's existing
  repeat-KOT/stock-deduction logic applies unchanged). A guest can call this
  repeatedly across multiple ordering rounds exactly like a cashier tapping "Add to
  KOT" again — no new mechanic.
- `GET /api/v1/guest/order-status` — polls `kot_service.list_active_tickets` filtered
  to the guest's own `order_id`, or connects to the existing
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
  round-off a real `POST /bills` would (reuses whatever pure calculation
  `bill_service` already factors out for Phase 09's on-screen preview), returns it
  read-only. No `bills` row is created here.
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
  into the existing bill-finalize path to also close any `guest_sessions` row pointing
  at the just-billed order) — the table's QR is then a clean slate for the next guest.

### 5. Settings + QR provisioning

- New Settings tab/section (`tenant_admin`, visible only when
  `meData.features?.qr_self_order === true`, same visibility pattern as Phase 22's
  Stock tab), scoped by the same location switcher Phase 10's Settings page already
  has for multi-location tenants — a Pro Max tenant with several branches manages and
  prints each location's own tables' QR codes separately, never a single flat list
  spanning locations. Within the selected location: a per-table "Generate QR" action
  (creates the `table_qr_codes` row, stamped with that table's own `location_id`, if
  missing; shows a printable QR + the table number) and a tenant-wide on/off switch
  (`tenants.qr_self_order_enabled`, default `false` — same additive-toggle shape as
  `waiter_mandatory_enabled` from Phase 24) so a Pro Max tenant can have the feature
  available but not yet turned on for the floor.
- `/auth/me` gains `qr_self_order_enabled` (effective flag: plan feature AND tenant
  toggle, same computed-flag convention as `stock_tracking_enabled`).

### 6. Frontend — a second, separate client, not a mode of the POS app

- New route tree mounted outside the existing authenticated shell entirely — no
  sidebar, no login page, no `ProtectedRoute`: `/order/:qrToken` (scan landing) →
  `/order/:qrToken/menu` → `/order/:qrToken/cart` → `/order/:qrToken/status` →
  `/order/:qrToken/bill`. Guest JWT stored the same way the staff app stores tokens
  (`localStorage`, via a **separate** key so a guest session on a shared/kiosk device
  can never collide with or be read as a staff session).
- Reuses `ItemCard.tsx`'s stock-badge/out-of-stock visuals and Indian-number-formatting
  helpers (`formatINR`) as-is; does **not** reuse `CartPanel.tsx`/`TableWaiterBar.tsx`
  wholesale (those assume a logged-in staff role and hotkeys) — a new, minimal
  `GuestCart.tsx`/`GuestOrderStatus.tsx`/`GuestBillPreview.tsx` built for one-handed
  phone use, same network-tolerant "Saving…/Saved" indicator CLAUDE.md §9 already
  requires for the waiter's mobile flow (guests are on the same patchy restaurant
  Wi-Fi).
- Staff side: `KotTicketsPopup.tsx`/Kitchen Display gain the "📱 Self-order" badge
  (§1); POS/Dashboard gain a toast/sound on the existing location websocket's new
  `payment_claimed` message so a cashier is actively notified rather than needing to
  notice a status change.

## Acceptance Criteria

- Scanning a table's QR with no existing active session creates one and lands on the
  menu with no login/signup screen of any kind; name/phone are always skippable.
- A second phone scanning the same table's QR while a session is already active joins
  that same cart (verified by both seeing the same items), not a second competing one.
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
  calling `POST /bills` directly gets 403 (it isn't even a valid token type for that
  route's dependency).
- Tapping "Pay via UPI" opens the guest's own UPI app pre-filled with the correct
  amount; no QR image is shown to the guest.
- The synthetic per-tenant system account never appears in `GET /api/v1/users`, never
  counts against the plan's seat cap, and never accrues incentive — but its bills do
  show up as their own row in Cashier-wise Sales/Incentive with ₹0 incentive.
- Turning the tenant's QR toggle off immediately 401/redirects any in-flight guest
  session's next request with a clear "ordering is currently unavailable" message,
  without deleting `table_qr_codes` rows (same soft-disable convention as every other
  tenant toggle in this codebase).
- Lite/Pro tenants: no QR Settings tab, `/auth/me`'s `qr_self_order_enabled` is always
  `false`, and every `/api/v1/guest/*` route 403s regardless of a valid-looking guest
  token, since the plan-feature check happens before the token is even trusted for
  anything beyond identifying the tenant.
