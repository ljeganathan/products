---
description: Phase 4 - Frontend app shell, routing, auth screens, RBAC guards, i18n, design system
---

# Phase 4 — Frontend Foundation

Before writing any component, read `/mnt/skills/public/frontend-design/SKILL.md`
equivalent guidance (apply the same principles Claude Code has access to
locally under its own skills) to avoid a generic admin-template look — this
product should feel colorful, modern, and retail-friendly, not like a grey
B2B dashboard. Read `CLAUDE.md §5 and §7` for RBAC and localization rules.

## Tasks

1. **Design tokens**: Tailwind theme extension with a distinct StoreMate TN
   palette (e.g. a warm primary accent + a clear success/danger/warning set
   for stock states), typography scale, and touch-friendly sizing (min
   44px tap targets throughout — this runs on tablets).
2. **App shell**: `layouts/AppLayout.tsx` (sidebar/topbar for
   admin/product_owner), `layouts/PosLayout.tsx` (distraction-free
   full-screen layout for the POS screen — no persistent sidebar, POS is a
   dedicated full-viewport experience per the product requirement).
3. **Routing**: React Router v6 route tree:
   - `/login`
   - `/dashboard` (admin default landing page; pos_user has no dashboard access)
   - `/pos` (pos_user, admin)
   - `/stock` (admin, read-only for pos_user)
   - `/items`, `/categories` (admin)
   - `/settings/*` (admin)
   - `/users` (admin)
   - `/reports` (admin, pos_user sees own-shift subset)
   - `/owner/*` (product_owner console — tenants, plans, subscriptions, platform dashboard)
   - `RequireAuth` + `RequireRole` route wrappers implementing the exact
     matrix from `CLAUDE.md §5`; unauthorized access redirects with a toast,
     not a blank page.
4. **Auth screens**: Login page (email/password), token refresh handled
   transparently via an axios interceptor in `api/client.ts`, persisted
   session in memory + httpOnly-safe pattern (refresh token handling
   documented; access token kept in memory, not localStorage, to reduce XSS
   risk).
5. **State/data layer**: Zustand slice for `authStore` (user, role, tenant,
   plan), TanStack Query client configured with sane defaults (staleTime
   tuned for item cache to support fast POS search).
6. **i18n**: `i18n/en.json`, `i18n/ta.json` seeded with all shell strings
   (nav labels, buttons, common words). Language toggle wired to the
   tenant's `Settings → Language` value (Phase 6 will connect the settings
   API; for now support a local toggle backed by the authStore/user
   preference field already in the model).
7. **Shared components**: Button, Input, Table (paginated, searchable),
   Modal, Toast, Badge (for plan tier and stock status), EmptyState,
   PageHeader — built with shadcn/ui primitives + Tailwind, used
   consistently across later phases.
8. **Responsive/tablet targets**: verify shell layout at 1280×800 (desktop)
   and 1024×768 / 820×1180 (common tablet sizes) — sidebar collapses to a
   bottom/top compact bar on tablet widths, POS layout stays full-screen at
   all supported widths.

## Definition of Done
- [ ] Login flow works end-to-end against Phase 2 backend for all 3 roles
- [ ] Route guards correctly block/redirect per the role matrix
- [ ] Language toggle switches all shell strings between en/ta instantly
- [ ] Shared component library renders consistently at desktop + tablet widths
- [ ] No hardcoded English/Tamil strings outside `i18n/*.json` in shell code
- [ ] Lighthouse/manual check: interactive shell loads in a reasonable time on a mid-range tablet profile
