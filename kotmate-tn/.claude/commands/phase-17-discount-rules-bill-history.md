# /phase-17-discount-rules-bill-history

Read `CLAUDE.md` §6, §9 before starting.

## Goal
Two small, independent fixes from manual testing: make a discount rule's type visible (and its coupon code reachable) while editing, and give Bill History filters that match how a TN floor actually organizes tables (by seating section) plus a cashier filter alongside the existing waiter filter.

## Scope
1. **Discount Rules** (`DiscountRulesPage.tsx`)
   - The Type selector was hidden entirely once editing an existing rule (only shown when adding), so an admin editing a coupon-type rule had no visible confirmation of its type — the coupon-code field itself was already correctly gated on `form.type === "coupon"` and did render, but with no visible label explaining why. Fix: always render the Type field, disabled (not hidden) once editing, with a note that type can't change after creation. Also handles the edge case where a rule's type is no longer in the tenant's current `allowedTypes` (e.g. downgraded from Pro Max after a coupon rule already existed) by still listing that rule's actual type as an option.
2. **Bill History** (`BillHistoryPage.tsx`, backend `GET /api/v1/bills`)
   - Backend: `BillSearchParams` gains `section_id` and `pos_user_id` — both already stored on every `Bill` row, just not exposed as search filters.
   - Frontend: the "All tables" dropdown is replaced with an "All sections" dropdown (AC/Non-AC/Rooftop/...), and a new "All cashiers" dropdown (tenant_admin + pos_user logins, since either can be the cashier-of-record) sits alongside the existing waiter filter.

## Acceptance Criteria
- Editing an existing coupon-type discount rule shows "Type: Coupon code" (disabled) and the coupon code field, pre-filled and editable.
- Filtering Bill History by seating section returns only bills billed under that section; filtering by cashier returns only bills where that user was the cashier-of-record. Both verified against the backend directly (not just the UI), and combinable with the existing date/waiter/bill-number filters.
