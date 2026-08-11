# Deployment — KOTMate TN on Hostinger VPS

This targets the existing Hostinger VPS (`187.127.129.35`,
`srv1721226.hstgr.cloud`, KVM 2) that already runs **n8n** (via its own
Traefik instance, bound to host ports 80/443) and **storemate-tn** deployed
alongside it on the same Traefik network. KOTMate TN joins that same VPS the
same way storemate-tn already does — a separate Docker Compose project, its
own Postgres, routed by hostname through the existing Traefik rather than
binding its own copy of ports 80/443.

Day-to-day development happens on Windows (`CLAUDE.md`), but the VPS itself
is Linux — every command below runs **over SSH on the VPS**, not the Windows
dev machine.

> Nothing here has been exercised against the real VPS yet. The Docker
> Compose stack builds and boots locally (backend gunicorn image, frontend
> nginx image, merged `docker-compose.prod.yml` + `docker-compose.traefik.yml`
> config) — the shape of every command below is standard
> Hostinger/Ubuntu/Docker/Traefik practice, matching what storemate-tn
> already runs successfully on this exact VPS. The certificate issuance and
> the final live smoke test are the two things that can only be verified on
> the real box.

## 0. Before you start: check headroom

Three stacks (n8n, storemate-tn, kotmate-tn) will now share this VPS. All
three are light (FastAPI/Postgres/nginx or equivalent), but KVM 2 is a
modest tier — do a quick sanity check before deploying:

```bash
free -h
docker stats --no-stream
df -h
```

If memory/disk is already tight, consider lowering `BACKEND_WORKERS` to 1
(see §3) before the first deploy rather than after something falls over.

## 1. Clone the repo and configure secrets

KOTMate TN is published into the same `ljeganathan/products` monorepo
storemate-tn already lives in (see kotmate-tn's own memory/CLAUDE.md notes on
the sync process — this doc assumes that repo is already the source of
truth on GitHub). On the VPS, reuse the same monorepo clone storemate-tn
already uses (or create one if this is the first product deployed):

```bash
# If a products/ clone doesn't already exist on this VPS:
git clone https://github.com/ljeganathan/products ~/products
cd ~/products/kotmate-tn

# If it already exists (storemate-tn was deployed first):
cd ~/products && git pull origin main
cd kotmate-tn
```

```bash
cp .env.example .env
nano .env   # fill in real POSTGRES_PASSWORD, APP_DB_PASSWORD, JWT_SECRET, etc.
```

Generate real secrets rather than leaving the placeholders:

```bash
openssl rand -base64 32   # → POSTGRES_PASSWORD
openssl rand -base64 32   # → APP_DB_PASSWORD
openssl rand -base64 48   # → JWT_SECRET
```

`.env` is gitignored — it never gets committed; production secrets live only
on the VPS and in GitHub Actions secrets (§6).

## 2. DNS

Point `app.kotmatetn.in` at the VPS's public IP (Hostinger hPanel → Domains
→ `kotmatetn.in` → DNS/Nameservers → add an **A record**, host `app`, value
`187.127.129.35`). No `www` record is needed since this is a subdomain, not
the apex — the apex domain stays free for a future marketing/landing page.

Verify it resolved: `dig +short app.kotmatetn.in` should print the VPS IP.

## 3. Find the existing Traefik network + certresolver

storemate-tn already answered this when it was deployed — reuse the same
values rather than re-deriving them:

```bash
cat ~/products/storemate-tn/.env | grep -E '^TRAEFIK_'
```

If that file isn't available for some reason, derive it directly:

```bash
docker network ls | grep -i n8n        # → the network name, e.g. n8n_default
docker ps --filter name=traefik --format '{{.Names}}'
docker inspect <traefik-container-name> --format '{{json .Args}}' | grep -o 'certificatesresolvers\.[a-zA-Z0-9]*'
```

Set `TRAEFIK_NETWORK` and `TRAEFIK_CERT_RESOLVER` in `.env` (§1) to whatever
you find.

## 4. First launch

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  -f docker-compose.traefik.yml up -d --build postgres backend nginx
```

Naming `postgres backend nginx` explicitly matters: it means Compose never
creates any service that binds host ports 80/443, so there's no collision
with n8n's Traefik. `nginx` here is KOTMate TN's own frontend container
(built from `frontend/Dockerfile`'s `prod` target) — it serves the built
static bundle and proxies `/api`, `/uploads`, `/ws` to `backend` itself
(`frontend/nginx.conf`), so it's the single origin Traefik needs to route
to; the existing Traefik discovers it via the Docker-label provider
(`docker-compose.traefik.yml`) and requests+attaches the TLS cert on the
first real request — give it a few seconds before testing.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  -f docker-compose.traefik.yml exec backend alembic upgrade head
```

Create the initial `product_owner` login (interactive prompt, no manual SQL
needed):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  -f docker-compose.traefik.yml exec backend python -m scripts.create_superuser
```

Visit `https://app.kotmatetn.in` — you should see the KOTMate TN login
screen over a valid TLS connection.

## 5. Redeploying (`scripts/deploy.sh`)

```bash
bash scripts/deploy.sh
```

Pulls `main` (the whole `products` monorepo checkout — this only affects
`kotmate-tn/`'s own containers, not storemate-tn's running ones), backs up
the DB (§7), rebuilds/restarts `postgres backend nginx` via
`docker compose up -d --build`, applies any new Alembic migrations, and
prunes dangling images.

**Windows-friendly note**: this is a VPS-only script (bash, `docker compose
exec`, etc.) — you won't run it from the Windows dev machine. From Windows
you have two options:
- **Automatic**: merge to `main` → CI's `deploy` job (§6) SSHes in and runs
  it for you.
- **Manual**: `ssh root@187.127.129.35 "cd ~/products/kotmate-tn && bash scripts/deploy.sh"`
  from PowerShell, or open a normal SSH session and run it there directly.

## 6. CI/CD — gated deploy job (not yet wired up)

storemate-tn's equivalent workflow lives at
`ljeganathan/products/.github/workflows/storemate-tn-deploy.yml` (root of
the monorepo — GitHub Actions only reads workflows from a repo's root).
KOTMate TN currently only has the CI-only workflow
(`.github/workflows/kotmate-tn-ci.yml`, no deploy job) — adding the deploy
job means replacing it with a combined "CI & Deploy" workflow, mirroring
storemate-tn-deploy.yml's shape:

- Same `backend`/`frontend` test jobs already in `kotmate-tn-ci.yml`.
- A `deploy` job gated on a GitHub **environment** named `production` with a
  required reviewer (so every deploy pauses for a manual click) — the same
  environment storemate-tn's deploy job already uses; adding kotmate-tn's
  secrets to it doesn't disturb storemate-tn's own secrets.
- New repo secrets (prefixed `KOTMATE_`, mirroring storemate-tn's own
  `STOREMATE_*` naming): `KOTMATE_DEPLOY_HOST`, `KOTMATE_DEPLOY_USER`,
  `KOTMATE_DEPLOY_SSH_KEY`, `KOTMATE_DEPLOY_PATH` (`~/products/kotmate-tn`
  on this VPS).

This is a deliberate follow-up step, not part of this scaffolding — it
touches the shared `products` repo root (outside `kotmate-tn/`) and needs
new secrets configured before it can run, so it's done as its own explicit
change once you're ready.

## 7. Backups (`scripts/backup_db.sh`)

```bash
bash scripts/backup_db.sh
```

Writes a `pg_dump -Fc` (custom format, restorable and supports
selective/parallel restore) to `./backups/kotmate_<timestamp>.dump` and
prunes anything older than 14 days (`RETENTION_DAYS` env var to change it).
`scripts/deploy.sh` already calls this before every redeploy; for a standing
daily backup independent of deploys, add a crontab entry:

```bash
crontab -e
# Daily at 2 AM VPS time:
0 2 * * * cd ~/products/kotmate-tn && bash scripts/backup_db.sh >> ~/kotmate-backup.log 2>&1
```

Copy backups off the VPS periodically too (Hostinger's own snapshot feature,
or `rsync`/`scp` to another host) — a backup that only ever lives on the
same disk as the database doesn't protect against VPS loss.

### Restore runbook

```bash
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.traefik.yml"

# Stop the backend so nothing writes to the DB mid-restore.
$COMPOSE stop backend

# Restore into the running postgres container. --clean drops existing
# objects first so this is safe against a DB that already has (wrong) data;
# --if-exists silences "does not exist" noise on a truly empty target.
$COMPOSE exec -T postgres \
  pg_restore -U kotmate -d kotmate --clean --if-exists \
  < ./backups/kotmate_<timestamp>.dump

$COMPOSE start backend
```

## 8. Final smoke test checklist (run against the live deployment)

- [ ] `https://app.kotmatetn.in` loads over a valid TLS connection.
- [ ] Log in as `product_owner`, a tenant `admin`, and a `pos_user` — each
      lands on the correct default route per `CLAUDE.md §5`.
- [ ] Complete a full POS sale: search an item, add to cart, finalize —
      server-recalculated total matches what the UI showed pre-submit.
- [ ] Kitchen Display / POS live updates work (`/ws/location/{id}` — confirm
      the websocket actually upgrades through the proxy, not just that the
      page loads: check the browser Network tab for a `101 Switching
      Protocols` response).
- [ ] Item image upload round-trips (`/uploads/...` served correctly through
      the proxy).
- [ ] Confirm storemate-tn's own domain still loads correctly after
      kotmate-tn's deploy — the shared Traefik/n8n stack shouldn't have been
      touched, but this is the cheap way to prove it.

This checklist requires a live deployment to actually execute — it has not
been run against the real VPS in this environment. Everything upstream of it
(image builds, compose config, migrations, the app's own test suite) has
been verified locally as documented above.
