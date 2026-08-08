# /phase-18-pos-core-fixes

Read `CLAUDE.md` §9, §11 before starting.

## Goal
Fix the batch of POS screen bugs and gaps found in manual testing: item images not rendering, a search box that silently failed on realistic short queries, category tabs that all looked identical, a "Top Selling" tab that never reflected actual sales, no way to see every item at once, dead-end empty sections in the table picker, no way to clear a mis-entered cart, KOT ticket contents hidden, incentive figures cluttering the cashier's screen, clunky payment entry, and no visible hotel/location context.

## Scope
1. **Images** — `item.image_url`/`category.icon_url`/`hotel.logo_url` are server-relative paths; a bare `<img src>` resolved them against the frontend's own origin instead of the backend that serves `/uploads`. New `resolveAssetUrl()` helper in `lib/api.ts`, applied everywhere an uploaded image renders.
2. **Search** — `POST /items/search`'s trigram-similarity-only match missed realistic short prefixes (e.g. "cof" vs "Filter Coffee" scores under pg_trgm's 0.3 default threshold). Backend now ORs in a plain `ILIKE` substring match alongside the existing trigram fuzzy match, keeping typo-tolerance while fixing the common case.
3. **Category icons** — new `categories.icon_url` (nullable, not plan-gated), upload endpoint mirroring the existing item-image pattern, exposed in Category Master; `CategoryNav.tsx` renders it when set, falling back to a generic icon.
4. **Dynamic Top Selling** — `list_top_sellers` now returns manually-pinned items (`is_top_seller`) first, backfilled with the tenant's actual best-sellers over the last 7 days (by billed quantity) when fewer than 8 are pinned. Frontend no longer re-filters the response to `is_top_seller` only, which was silently discarding the backfilled items.
5. **"All" category tab** — added to `CategoryNav.tsx`, placed after every real category (not right after "Top Selling") so it never shifts the existing F2-F9 hotkey-to-category index mapping.
6. **Empty sections hidden** — `TableWaiterBar.tsx`'s table picker now filters out any seating section with zero active tables instead of rendering a dead "No tables in this section" row.
7. **Esc + Clear cart** — `CartPanel.tsx` gets a "✕ Clear" button (visible whenever the cart isn't empty); `POSPage.tsx`'s Escape handler clears the search/item-code field first if either has text, otherwise clears the draft cart.
8. **KOT ticket expand/collapse** — `KotTicketsPopup.tsx` now renders each ticket as a `<details>` element showing its item list (name, Tamil name, quantity) when expanded, with a "Bill this ticket" action inside.
9. **Incentives off the POS screen** — the waiter/cashier incentive lines are removed from `CartPanel.tsx`'s bill summary entirely (they were never on the customer print; incentive data still flows into Phase 11 reports unchanged).
10. **Payment UX** — `BillingModal.tsx` auto-fills the single (non-split) payment row with the grand total via an effect keyed on `preview.grand_total`, removing the need for a manual "Fill full amount" click; the "+ Split Payment" control is now a full-size button instead of a small text link.
11. **Hotel/location visibility** — the POS header now shows the tenant's company name and the active location's name (from `/auth/me` and `/locations`) instead of a bare "POS" label.

## Acceptance Criteria
- An item/category/hotel-logo image uploaded through its admin screen renders correctly on the POS grid / category rail / bill print preview without a manual URL fix.
- Typing a realistic 3-4 letter prefix of an existing item's name in the POS search box returns that item.
- A category with an uploaded icon shows that icon on both the desktop rail and mobile/tablet strip; one without still shows the generic fallback.
- With nothing manually pinned, an item billed in the last 7 days appears under "Top Selling".
- The category rail has a final "All" tab showing every active item regardless of category.
- A seating section with zero active tables never appears in the table picker.
- Esc clears the draft cart when no field is focused; the "✕ Clear" button does the same via click, only shown when the cart has items.
- Expanding a KOT ticket shows its item list and a way to bill it directly.
- No incentive figures appear anywhere on the POS screen, for any role.
- Opening Finalize Bill pre-fills the payment amount with the grand total with no extra click; "+ Split Payment" is a full-size button.
- The POS header shows the tenant's company name and current location name.
