# /phase-08-kot-printing

Read `CLAUDE.md` §6, §10 before starting.

## Goal
KOT button/flow: send selected items to kitchen — physical KOT printer (Pro/Pro Max) and/or live Kitchen Display System (websocket, Pro/Pro Max), with a screen-only fallback KOT list for Lite. Kitchen-side viewing is restricted to the `kitchen` role ("KOT User" in UI copy, CLAUDE.md §5) — that login sees this screen and nothing else.

## Scope
1. **Backend**
   - `POST /api/v1/kot` — create a `kot_ticket` from the current order's new/unprinted items (supports repeat-KOT for add-on items ordered after the first KOT). Ticket header includes table number + section (e.g. "T5 (AC)") or the section name alone for Takeaway/Online Delivery, so kitchen staff know the order type at a glance. Callable by `waiter` or `pos_user` (either can be the one sending items to the kitchen) — `require_role("tenant_admin", "pos_user", "waiter")`.
   - `GET /api/v1/kot/tickets/active` — every open (parent order status `open`/`held`, not yet `billed`) ticket across the caller's location(s): ticket_number, table/section, item summary, status, created_at. Two consumers: the Kitchen Display (filtered to `new`/`preparing`/`ready`) and the Phase 07 billing screen's "KOT Tickets" popup (CLAUDE.md §11) — same query, no separate "billed" flag needed on the ticket since a ticket's parent order flipping to `billed` is what drops it from both views.
   - Printer abstraction (`app/printing/`): `escpos_thermal.py`, `dotmatrix_raw.py`, common `render_kot(ticket) -> bytes|text` per adapter, dispatched based on the tenant's configured KOT printer type.
   - WebSocket endpoint `/ws/location/{location_id}` (**not** `/ws/kitchen/...` — both the Kitchen Display *and* the Phase 07 POS grid connect to this one channel, so it's named for what it covers, not who was first to use it) broadcasting typed messages: `{"type": "kot_ticket", ...}` for new/updated tickets, and `{"type": "item_stock", "item_id", "available_qty", "low_stock", "out_of_stock"}` for the low-stock feature below. `kitchen` role can mark ticket `preparing`/`ready` — `require_role("kitchen", "tenant_admin")` (an admin can also work the kitchen screen if needed; `pos_user`/`waiter` cannot).
   - **Stock decrement on KOT send** (CLAUDE.md §11): when `POST /api/v1/kot` fires a ticket, for each ticket line whose item has `track_inventory=true`, decrement `items.available_qty` by the ticketed quantity (floor at 0, never negative) and broadcast an `item_stock` message on `/ws/location/{location_id}` — this is what keeps the KOT low-stock banner and the POS grid's greyed-out state in sync live, not just on next page load. Items without `track_inventory` are untouched, no decrement, no broadcast.
   - Gate physical printing behind plan check (`kot_printing` feature flag) — Lite tenants get an on-screen KOT ticket view only, no print dispatch.
2. **Frontend**
   - KOT button in POS cart — sends new items, shows confirmation toast with ticket number. Visible to `waiter` and `pos_user`; for `waiter` specifically this is one of only two order actions available (the other is Hold) — no Bill/print/payment control ever renders in a waiter's session (CLAUDE.md §9), and `POST /api/v1/bills` (Phase 09) independently rejects a `waiter`-role token server-side regardless of what the UI shows.
   - `/kot` Kitchen Display View (Pro/Pro Max) — **note the route is `/kot`, matching the `kitchen`-role home path already wired in Phase 02's router (`roleHomePath`), not `/kitchen`**: live-updating ticket board organized primarily by **ticket number** (table/section shown alongside each card, same convention as the printed ticket, CLAUDE.md §10), columns New / Preparing / Ready, large touch-friendly status buttons for kitchen staff. This is the *only* screen a `kitchen`-role login can reach — `router.tsx` scopes `/kot` to `roles={["tenant_admin", "kitchen"]}` separately from `/dashboard`/`/pos`'s `roles={["tenant_admin", "pos_user", "waiter"]}` (fixed post-Phase-02, once this gap was noticed), so `kitchen` can't reach `/dashboard`/`/pos` and `waiter`/`pos_user` can't reach `/kot`.
   - **Low-stock banner** on the Kitchen Display (CLAUDE.md §11): any tracked item at `available_qty <= 5` gets a persistent banner/badge (e.g. "⚠ Chicken 65 — 3 left") fed by `item_stock` messages on the same websocket connection the ticket board already holds open — no second socket. At `available_qty = 0` the banner reads "OUT" so kitchen staff know to flag it back to the floor immediately.
   - Settings sub-page (stub here, full settings page in Phase 10): register a KOT printer (type + connection).

## Acceptance Criteria
- Adding items after the first KOT and hitting KOT again only sends the new items (no duplicate print of already-fired items).
- Kitchen Display updates in real time across two browser tabs (simulating POS + kitchen screen).
- Lite tenant sees on-screen KOT ticket but no print dispatch attempt; Pro/Pro Max attempts actual print job via configured adapter (can be mocked/logged in dev without real hardware).
- A `kitchen`-role login can reach `/kot` but is redirected away from `/pos`, `/dashboard`, and any admin route.
- A `waiter`-role login has no visible or reachable path to finalize a bill; a direct `POST /api/v1/bills` call with a `waiter` token returns 403.
- `GET /api/v1/kot/tickets/active` reflects the same order the instant it's billed — it disappears from both the Kitchen Display and the billing screen's KOT Tickets popup without any extra client-side bookkeeping.
- Sending a KOT for a tracked item with `available_qty=7`, qty 3 in the ticket, drops it to 4 and both the Kitchen Display banner and a second open POS tab's item card update within the same session, no reload.
- A tracked item hitting `available_qty=0` greys out on the POS grid (Phase 07) in real time, even on a device that never fired the KOT itself.
