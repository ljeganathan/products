# /phase-06-waiter-master

Read `CLAUDE.md` §8 before starting.

## Goal
Waiter master, a Seating Sections master, and a Table master (tables tagged to a section) — all needed by the POS screen in Phase 07.

## Scope
1. **Backend** (`/api/v1/waiters/*`, `/api/v1/sections/*`, `/api/v1/tables/*`, tenant-scoped)
   - Waiter CRUD: `waiter_number` (unique per tenant/location), `name`, `phone` (optional), `incentive_rate` (%, per-waiter, used by POS to compute a per-bill incentive on net sale value — see Phase 07), `is_active`.
   - Seating Sections CRUD: `name_en`, `name_ta`, `is_seating` (bool — true for AC/Non-AC/Rooftop/Family-style physical seating; false for Takeaway/Online Delivery, which don't need a table number), `display_order`, `is_active`. New tenants are seeded with sensible defaults (AC, Non-AC, Rooftop, Family, Takeaway, Online Delivery) at tenant creation (Phase 03) — this screen lets `tenant_admin` rename, reorder, add, or deactivate them.
   - Table CRUD: `table_number`, `location_id`, `section_id` (**required** FK to seating_sections — only sections with `is_seating=true` are selectable here), `seating_capacity` (optional), `status` (free/occupied/billed) — status updates are driven by POS/order flow later, but the master data (add/edit/delete tables) belongs here.
2. **Frontend** (`/admin/waiters`, `/admin/sections`, `/admin/tables`)
   - Simple list + add/edit/delete forms for all three, consistent with the Item/Category master UI pattern from Phase 05.
   - Table add/edit form includes a required section dropdown; the table list shows each table's section as a colored tag for quick scanning.

## Acceptance Criteria
- Waiter number uniqueness enforced per tenant with a friendly duplicate error.
- Deleting a waiter with existing historical orders is soft-deactivate, not hard delete (same pattern as Phase 04 users).
- Every table must have a section assigned before it can be saved; a non-seating section (e.g. Takeaway) cannot be assigned to a physical table row.
- A tenant's default sections exist immediately after tenant creation with no manual setup required, and are editable/reorderable here.
