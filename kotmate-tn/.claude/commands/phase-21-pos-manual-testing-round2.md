# /phase-21-pos-manual-testing-round2

Read `CLAUDE.md` §5, §6, §9, §11 before starting.

## Goal
Fix a second round of hands-on manual-testing findings against the POS screen and Item Master: undersized header text, missing Tamil on category tabs, a cluttered top bar, a search box that only filtered the grid instead of offering a dropdown, no keyboard support in the Finalize Bill modal, no way to preview a bill before it prints, a cart that didn't clear after sending to KOT, a confusing open-ended "Party 1/Party 2" table-picker, and a missing Import CSV button for Pro-tier tenants that turned out to be correct (but too strict) plan gating rather than a bug.

## Scope
1. **Header sizing** — `POSPage.tsx`'s company-name/location text bumped from `text-[13px]`/`text-[10px]` to `text-base`/`text-xs`.
2. **Category Tamil names** — `CategoryNav.tsx`'s `NavEntry` gains `name_ta`, rendered under the English name in both rail and strip variants, matching `ItemCard.tsx`'s existing bilingual pattern.
3. **Top bar cleanup** — `POSPage.tsx` drops Reports/Bill History from `<UserMenu>` entirely (still reachable from the Dashboard's own nav) and adds a standalone "📊 Dashboard" button styled like the existing "KOT Tickets" button, for both `tenant_admin` and `pos_user`.
4. **Search dropdown** — new type-ahead results panel under the search box (full keyboard nav: arrows to highlight, Enter to add, Esc/click-outside to close), reusing the existing `handleAddItem` cart mutation rather than duplicating it. The existing "type to filter the grid" behavior is untouched — this is additive.
5. **Finalize Bill keyboard** — `BillingModal.tsx` gains a window-level Esc/Enter handler (Esc closes/cancels, Enter triggers whichever action is currently primary), guarded so it doesn't fire while a text/number/select input is focused.
6. **Optional print preview** — new `skip_print` flag on `BillCreateRequest`/`finalize_bill()`; when a new "Show print preview before printing" checkbox is on, the bill finalizes without dispatching to the printer, shows a preview screen, and the existing `POST /bills/{id}/reprint` endpoint (already used for after-the-fact reprints) is reused to actually print once confirmed — no new print-dispatch code path.
7. **Add-to-KOT clears the draft** — `handleSendKot` now mirrors `handleHold`'s clearing pattern (order/table/customer/waiter all reset locally; the order stays open server-side).
8. **Table + Customer selection redesign** — the reactive "tap an occupied table → Party N picker" modal (`PartyPickerView`) is removed. Every table tap now resolves immediately; a new always-visible `CustomerSelectorBar.tsx` component (same visual family as "Assign Waiter") shows numbered chips bounded by the table's `seating_capacity` (default 4), auto-selecting Customer-1. The underlying `orders.party_label` column is unchanged — only the label values ("Customer-N" instead of "Party N") and the picker UX changed. The selected customer label is threaded through end-to-end for the first time: `KotTicketRenderData`/`BillRenderData` (new `party_label` field, composed into `header_label` as "T5 Customer-2 (AC)"), the Kitchen Display card and KOT Tickets popup, the POS cart summary badge, and a new `bills.party_label` column (snapshotted at finalize time like `table_id`/`section_id`/`waiter_id`).
9. **Item Master Import CSV for Pro tier** — product decision: Pro tenants get CSV import too now, not just export (only Lite remains without it). A new data-only Alembic migration JSONB-merges `item_import: true` onto the seeded `pro` plan row; no application code changed since the frontend/backend were already correctly gating off this exact flag.
10. **Incidental** — none; unlike Phase 20, no pre-existing unrelated bugs were found while implementing this round.

## Acceptance Criteria
- Header text is visibly larger without breaking truncation on long names.
- Category tabs show Tamil names wherever set.
- POS top bar has exactly KOT Tickets / Recall / Dashboard, no Reports/Bill History links, for cashier and admin alike.
- Search produces a real dropdown with full keyboard support; the item grid's own filter-on-type behavior is unaffected.
- Esc/Enter work correctly at every stage of the Finalize Bill modal, including the new print-preview screen.
- Print-preview checkbox, when on, finalizes the bill (one bill_number, one row) without printing until an explicit Print click; when off, behavior is byte-for-byte the same as before this phase.
- Sending to KOT clears the on-screen draft; the order remains resumable.
- Selecting a table shows a capacity-bounded Customer bar, not a reactive modal; switching customers swaps carts independently; the table only frees once every customer has billed.
- "Table-N Customer-M" appears correctly on the KOT ticket (print + KDS + popup), the POS cart summary, and the printed bill.
- Pro-tier tenants see and can use Item Master's Import CSV button; Lite tenants still see neither Import nor Export.
