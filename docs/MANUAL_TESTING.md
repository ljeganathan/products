# Manual Testing Guide — Local Docker

This is the checklist for exercising StoreMate TN by hand against your local
Docker Compose stack, role by role and screen by screen. Use it after any
non-trivial change, before merging, or whenever you just want to poke at the
app.

Related: `docs/DEPLOYMENT.md` has the *production* smoke-test checklist
(run against a live Hostinger deployment). This doc is the local/dev
equivalent, with seeded demo data and no TLS/domain involved.

---

## 1. Get Docker running the latest code

The dev compose file (`docker-compose.yml`) bind-mounts your working tree
into both containers, so most code edits (backend Python, frontend
TS/TSX) show up live via `--reload` / Vite HMR without any rebuild. You
only need to rebuild when **dependencies** change (`requirements.txt`,
`package.json`) or you're not sure the containers picked up recent changes.

```powershell
# From the repo root
docker compose up -d --build      # rebuilds images if requirements/package.json changed
docker compose exec backend alembic upgrade head   # apply any new migrations
```

Verify the stack is actually current and healthy:

```powershell
docker compose ps                                   # both backend + frontend "Up"
docker compose exec backend alembic current          # should print "(head)"
curl http://localhost:8000/docs                      # 200 = backend API up
curl http://localhost:5173/                           # 200 = frontend dev server up
```

If you pulled new commits and want a clean slate:

```powershell
docker compose down
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

This does **not** wipe the `db_data` volume — your data survives. Use
`docker compose down -v` only if you intentionally want to drop the local
database too (you'll need to reseed afterward).

## 2. Seed demo data

The seed script isn't bind-mounted into the backend container, so copy it
in before running:

```powershell
docker compose cp scripts/seed_dev_data.py backend:/tmp/seed_dev_data.py
docker compose exec backend sh -c "cd /app && PYTHONPATH=/app python /tmp/seed_dev_data.py"
```

It's safe to re-run — it skips seeding if the demo tenant already exists.
It creates:

- **Tenant**: "Demo Store Chennai" with all 3 plans available (`lite`,
  `pro`, `pro_max`) and one store
- **3 users** (one per role, see credentials below)
- **5 categories**, **4 tax profiles** (0/5/12/18% + a default), **15 FMCG
  items** with opening stock and barcodes `890000000001`–`890000000015`

## 3. Login credentials (seeded demo tenant)

| Role | Email | Password |
|---|---|---|
| `product_owner` | `owner@storematetn.in` | `Owner@123` |
| `admin` | `admin@demostorechennai.in` | `Admin@123` |
| `pos_user` | `cashier@demostorechennai.in` | `Cashier@123` |

The demo tenant is created on the **Pro** plan by default — to test
plan-gating (Lite/Pro upgrade banners, blocked features), use the
`product_owner` console to change the tenant's plan (§6 below), then log
back in as `admin`/`pos_user` to see the gating take effect.

## 4. URLs

- Frontend: http://localhost:5173
- Backend API docs (Swagger): http://localhost:8000/docs
- Backend base URL: http://localhost:8000/api/v1

---

## 5. Role-by-role manual checklist

### 5.1 `pos_user` (cashier@demostorechennai.in)

- [ ] Log in → redirected straight to `/pos` (no dashboard/sidebar access)
- [ ] `/pos` loads in the full-screen POS layout (no persistent sidebar)
- [ ] Add an item via **fast search** (type "rice", arrow-navigate results, Enter)
- [ ] Add an item via **barcode/manual entry** field — type `890000000002` + Enter (Toor Dal)
- [ ] Adjust quantity on a cart line with `+`/`-`
- [ ] Remove a line with `Delete`, undo with `Ctrl+Z`
- [ ] Apply a bill-level discount (`F4`)
- [ ] Press `F1` — shortcut help overlay appears and matches on-screen buttons
- [ ] Finalize a sale (`F10` / `Ctrl+Enter`) — confirm the total shown matches the receipt preview (server-recomputed, not just the client's live total)
- [ ] Hold a bill (`F8`), start a new one, recall the held bill (`F9`)
- [ ] Preview a thermal (80mm) receipt and a dot-matrix receipt for the same bill
- [ ] Search saved bills — confirm only bills within the plan's window are visible (7 days on Lite)
- [ ] Try navigating directly to `/items`, `/settings`, `/users`, `/owner` by URL — confirm redirect + toast, not a blank page or crash
- [ ] `/stock` is visible but read-only (no add/edit controls)
- [ ] `/reports` shows only this cashier's own shift, not the whole store

### 5.2 `admin` (admin@demostorechennai.in)

- [ ] Log in → redirected to `/dashboard`
- [ ] Dashboard shows today's sales, bill count, top 5 items, low-stock count
- [ ] On Pro/Pro Max plan: date-range picker, trend chart, category/cashier/payment-mode breakdown all render
- [ ] `/items` — create a new item with both `name_en` and `name_ta` filled in; barcode "scan to fill" works
- [ ] `/items` — bulk CSV import: upload a file with a few intentionally bad rows, confirm row-level errors are reported (not a blanket failure)
- [ ] `/categories` — add a parent + child category (e.g. Dairy → Curd)
- [ ] `/stock` — adjust stock on an item with a reason (purchase/adjustment/return/damage), confirm the change is reflected immediately and appears in movement history
- [ ] `/stock/low-stock` — lower an item's quantity below its reorder level, confirm it appears here and the notification bell picks it up (Pro/Pro Max only; Lite shows an upgrade prompt)
- [ ] `/users` — add a new `pos_user`, confirm they can log in; try exceeding the plan's user limit and confirm it's blocked with a clear message
- [ ] `/settings/tax` — add/edit a tax profile, mark one as default
- [ ] `/settings/printer` — add a printer profile, use "Test Print", confirm it renders correctly
- [ ] `/settings/company` — update company name/GSTIN/logo, confirm the logo shows up in the print preview
- [ ] `/settings/language` — toggle Tamil/English, confirm shell strings switch instantly
- [ ] `/settings/discounts` — create an item-level discount rule (Pro+ only; Lite shows upgrade prompt)
- [ ] `/settings/subscription` — view current plan/usage, submit an upgrade request
- [ ] `/reports` — pull a date-range sales report and a GST summary; export CSV (Pro/Pro Max only)
- [ ] Full POS flow also works for `admin` (same as §5.1, since admin has POS access too)

### 5.3 `product_owner` (owner@storematetn.in)

- [ ] Log in → redirected to `/owner` (platform dashboard: tenant count, MRR, plan mix, churn, overdue invoices)
- [ ] `/owner/tenants` — see the demo tenant, view its usage vs plan limits, suspend then reactivate it
- [ ] `/owner/plans` — edit a plan's price or limits, confirm it's reflected when a tenant on that plan reloads
- [ ] `/owner/subscriptions` — change the demo tenant's plan (e.g. Pro Max → Lite), then log in as `admin` in another browser/incognito tab and confirm gated features (multi-store, dashboard range, discount rules, API access) immediately disappear/show upgrade prompts
- [ ] Try downgrading a tenant below its current usage (e.g. to Lite's 2-user cap when it has 3 users) — confirm it's blocked with a clear message
- [ ] `/owner/invoices` — generate the next invoice for the demo tenant, mark it paid
- [ ] `/owner/maintenance` — enable maintenance mode, confirm `admin`/`pos_user` sessions see a maintenance banner/block screen while `product_owner` does not; disable it again afterward
- [ ] Confirm `product_owner` cannot see `/pos`, `/items`, `/stock`, `/users` (own-tenant screens) — only platform-level screens

---

## 6. Cross-cutting checks

- [ ] **i18n**: switch language in Settings, confirm POS, stock, and item/category screens fully relabel — no stray hardcoded English/Tamil text
- [ ] **Tablet width**: resize browser (or DevTools device toolbar) to 1024×768 — POS stays full-screen and usable with no horizontal scroll; sidebar collapses appropriately on the admin shell
- [ ] **Token refresh**: stay logged in past the access-token expiry (30 min) and confirm a request still succeeds transparently (refresh handled by the axios interceptor) rather than bouncing you to `/login`
- [ ] **Tenant isolation**: if you seed a second tenant, confirm neither admin nor pos_user of one tenant can see the other's data via any screen or direct API call
- [ ] **Plan gating is server-enforced**: with browser devtools, try calling a gated endpoint directly (e.g. `GET /api/v1/dashboard/trend` while on Lite) — must 403, not just be hidden in the UI

---

## 7. Resetting between test runs

To start over with a clean database:

```powershell
docker compose down -v          # drops db_data volume too
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose cp scripts/seed_dev_data.py backend:/tmp/seed_dev_data.py
docker compose exec backend sh -c "cd /app && PYTHONPATH=/app python /tmp/seed_dev_data.py"
```

## 8. Automated checks (run before/alongside manual testing)

```powershell
docker compose exec backend python -m pytest
docker compose exec backend python -m ruff check .
docker compose exec backend python -m mypy app
docker compose exec frontend npm run test
docker compose exec frontend npm run lint
```

These catch regressions in billing math, RBAC guards, and plan-limit logic
fast — manual testing above is for the things automated tests don't cover:
actual UX flow, print preview rendering, and cross-role visual gating.
