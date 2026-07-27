# Deployment — StoreMate TN on Hostinger VPS

Everything below targets a fresh Ubuntu 22.04/24.04 Hostinger VPS. Day-to-day
development happens on Windows (per `CLAUDE.md`), but the VPS itself is
Linux, and every command in this doc runs **over SSH on the VPS**, not on
the Windows dev machine — the "Windows-friendly notes" callouts mark the
few places that differ.

> **What this doc has NOT been verified against**: an actual Hostinger VPS,
> a real domain, or a real DNS record. Everything here has been verified as
> far as this dev environment allows — the Docker Compose stack builds and
> boots locally (backend gunicorn image, frontend static image, merged
> `docker-compose.prod.yml` config), and the shape of every command below
> is standard Hostinger/Ubuntu/Docker/certbot practice. The one thing that
> is genuinely unverifiable without a real VPS + domain is the certbot TLS
> issuance step and the final live smoke test — both are called out below.

## 1. Initial server setup

SSH in as the Hostinger-provided root user, then:

```bash
apt update && apt upgrade -y
adduser deploy && usermod -aG sudo deploy
# Log back in as `deploy` from here on — don't run the stack as root.
su - deploy
```

Point your domain's DNS **A record** at the VPS's public IP before
continuing (propagation can take a few minutes to a few hours):

| Type | Host | Value |
|---|---|---|
| A | `@` (or `storematetn.in`) | `<VPS public IP>` |
| A | `www` | `<VPS public IP>` |

Verify it resolved: `dig +short storematetn.in` should print the VPS IP.

## 2. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker deploy
newgrp docker
docker --version && docker compose version
```

## 3. Clone the repo and configure secrets

```bash
git clone <your-repo-url> ~/storemate-tn
cd ~/storemate-tn
cp .env.example .env
nano .env   # fill in real POSTGRES_PASSWORD, JWT_SECRET, DOMAIN, CORS_ORIGINS, etc.
```

Generate real secrets rather than leaving the placeholders:

```bash
openssl rand -base64 32   # → POSTGRES_PASSWORD
openssl rand -base64 48   # → JWT_SECRET
```

`.env` is gitignored at the repo root (see `.gitignore`) — it never gets
committed, and production secrets live only on the VPS and in GitHub
Actions secrets (§7).

## 4. Initial TLS bootstrap (the certbot chicken-and-egg step)

`docker/nginx.conf` references `ssl_certificate` files under
`/etc/letsencrypt/live/$DOMAIN/` that don't exist yet on a fresh box —
nginx refuses to start without them, and certbot's webroot method needs
nginx already serving port 80 to complete the HTTP-01 challenge. Break the
cycle with a one-off standalone certbot run **before** the first
`docker compose up`:

```bash
sudo docker run --rm -p 80:80 \
  -v storemate-tn_certbot_certs:/etc/letsencrypt \
  certbot/certbot certonly --standalone \
  -d storematetn.in -d www.storematetn.in \
  --email you@example.com --agree-tos --no-eff-email
```

(Volume name must match the one Compose will create —
`storemate-tn_certbot_certs`, i.e. `<project-dir-name>_certbot_certs`; if
your clone directory isn't named `storemate-tn`, adjust accordingly or run
`docker compose config --volumes` after step 5 to confirm the name first.)

This writes real certs into the `certbot_certs` volume that the `nginx` and
`certbot` services in `docker-compose.prod.yml` will reuse from here on —
the `certbot` service's `certbot renew` loop (already wired into the
compose file) handles auto-renewal every 12 hours from this point forward,
so this standalone step is a **one-time bootstrap only**, never repeated.

## 4b. Alternative: deploying alongside an existing Traefik-fronted stack

Skip this section (and step 4 above) if StoreMate TN owns the whole VPS.
Use this instead if another stack (e.g. n8n's own `docker-compose.yml`,
using the standard n8n "Traefik" template) already has a Traefik container
bound to host ports 80/443 — you cannot also bind nginx+certbot to those
same ports, and you don't need to: the existing Traefik already has a
Let's Encrypt certresolver configured, and it will issue a certificate for
StoreMate TN's domain too, automatically, the first time it's requested —
no separate certbot/webroot bootstrap step at all.

1. Confirm the existing Traefik's setup — find its compose file (e.g.
   `/docker/n8n/docker-compose.yml`) and note two things from it:
   - The Docker network name Traefik is on (Compose's default network
     naming is `<project-dir-name>_default`, e.g. `n8n_default` —
     `docker network ls` confirms it).
   - The `certresolver` name from its `--certificatesresolvers.<name>.acme...`
     command flags (e.g. `mytlschallenge`).
2. Point `DOMAIN`'s DNS A records (`@` and `www`) at the VPS IP, same as
   step 1 above — this is still required regardless of which nginx/Traefik
   path you use.
3. In `.env`, set `TRAEFIK_NETWORK` and `TRAEFIK_CERT_RESOLVER` to the
   values found in step 1.
4. Skip straight to step 5 below, but only start `db`, `backend`, and
   `frontend` — passing those service names explicitly means Compose never
   creates `nginx`/`certbot` at all, so there's no port collision:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
     -f docker-compose.traefik.yml up -d --build db backend frontend
   ```
   `frontend`'s own nginx (`frontend/nginx.conf`) already proxies `/api/`
   and `/media/` to the backend itself in this topology — it's the sole
   public origin behind Traefik, unlike the standalone-nginx path where a
   separate proxy tier does that job.
5. The existing Traefik discovers the new `frontend` container via its
   Docker-label provider (labels come from `docker-compose.traefik.yml`)
   and requests+attaches the TLS cert on the first real request to the
   domain — give it a few seconds after `docker compose up` before testing.

## 5. First launch

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Visit `https://storematetn.in` — you should see the StoreMate TN login
screen over a valid TLS connection. If nginx fails to start, re-check step
4 — it almost always means the cert files aren't where `docker/nginx.conf`
expects them.

Seed the product-owner account (see `scripts/seed_dev_data.py` for the
dev-fixture equivalent; production instead needs one real `product_owner`
row created directly — see `docs/DATABASE_SCHEMA.md §users` for the shape,
or run a one-off Python shell via
`docker compose ... exec backend python` to insert it through
`app.services.auth_service`-compatible hashing).

## 6. Redeploying (`scripts/deploy.sh`)

```bash
bash scripts/deploy.sh
```

This pulls `main`, backs up the DB (§8), rebuilds/restarts every service via
`docker compose up -d --build`, applies any new Alembic migrations, and
prunes dangling images. It's "zero-downtime-ish": Compose recreates
containers one service at a time, so there's a few seconds of backend
unavailability during the swap, not a full-stack outage.

**Windows-friendly note**: you won't run `deploy.sh` from your Windows dev
machine — it's a VPS-only script (bash, `docker compose exec`, etc., none
of which need a Windows twin per `CLAUDE.md §3`'s "no bash-only tooling"
rule, since that rule targets scripts a Windows developer runs locally).
From Windows you have two options:
- **Automatic**: merge to `main` → CI's `deploy` job (§7) SSHes in and runs
  it for you.
- **Manual**: `ssh root@<vps-ip> "cd /docker/products/storemate-tn && TRAEFIK_MODE=1 bash scripts/deploy.sh"`
  from PowerShell (adjust the path/user/`TRAEFIK_MODE` to match your actual
  setup per §4b), or open a normal SSH session and run it there directly.

## 7. CI/CD — gated deploy job

The workflow that actually runs on GitHub lives at
`ljeganathan/products/.github/workflows/storemate-tn-deploy.yml` (path-filtered
to `storemate-tn/**`), **not** `storemate-tn/.github/workflows/ci.yml` —
GitHub Actions only reads workflows from a repo's root, and this code only
exists on GitHub as a subtree inside the `products` monorepo (synced via
`scripts/push_to_products.*`). The local `ci.yml` is kept as the
authoritative reference for what the test jobs should run; keep both in
sync if either changes. Its `deploy` job runs after `backend` and
`frontend` both pass, only on a push to `main`, and only after a manual
approval (via a GitHub **environment** named `production`). One-time setup
(on the `products` repo, not `storemate-tn`):

1. Repo Settings → Environments → New environment → `production`.
2. Add yourself (or the team) as a **required reviewer** — this is what
   makes every deploy pause for a manual click, appropriate for a paid
   customer-facing app.
3. Add these secrets to the `production` environment (prefixed
   `STOREMATE_` since other products may share this monorepo/environment
   later):
   - `STOREMATE_DEPLOY_HOST` — the VPS IP or hostname
   - `STOREMATE_DEPLOY_USER` — `root` on the current VPS (it only has a
     root account; a dedicated non-root `deploy` user is the more
     conventional setup elsewhere, per step 1, but wasn't set up on this
     box before StoreMate TN was added to it)
   - `STOREMATE_DEPLOY_SSH_KEY` — a private key whose public half is
     authorized on the VPS (generate a dedicated
     deploy-only keypair, don't reuse a personal one)
   - `STOREMATE_DEPLOY_PATH` — `/docker/products/storemate-tn` on the
     current VPS (a clone of the `products` monorepo, following that box's
     existing `/docker/<stack>` convention — see §4b)

Once configured: merging to `main` runs tests, then waits for approval,
then SSHes in and runs `scripts/deploy.sh`.

The `production` environment, its 4 secrets, and the required reviewer are
confirmed set up on `ljeganathan/products` as of 2026-07-27.

## 8. Backups (`scripts/backup_db.sh`)

```bash
bash scripts/backup_db.sh
```

Writes a `pg_dump -Fc` (custom format, restorable and supports
selective/parallel restore) to `./backups/storemate_<timestamp>.dump` and
prunes anything older than 14 days (`RETENTION_DAYS` env var to change it).
`scripts/deploy.sh` already calls this before every redeploy; for a
standing daily backup independent of deploys, add a crontab entry:

```bash
crontab -e
# Daily at 2 AM VPS time:
0 2 * * * cd /home/deploy/storemate-tn && bash scripts/backup_db.sh >> /home/deploy/backup.log 2>&1
```

Copy backups off the VPS periodically too (Hostinger's own snapshot
feature, or `rsync`/`scp` to another host) — a backup that only ever lives
on the same disk as the database doesn't protect against VPS loss.

### Restore runbook

```bash
# Stop the backend so nothing writes to the DB mid-restore.
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop backend

# Restore into the running db container. --clean drops existing objects
# first so this is safe to run against a DB that already has (wrong) data;
# --if-exists silences "does not exist" noise on a truly empty target.
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  pg_restore -U storemate -d storemate --clean --if-exists \
  < ./backups/storemate_<timestamp>.dump

docker compose -f docker-compose.yml -f docker-compose.prod.yml start backend
```

**Tested locally** (stand-in for the VPS, same Postgres 15 image): seeded
the dev DB via `scripts/seed_dev_data.py`, ran `pg_dump -Fc` against it,
dropped and recreated the database, then `pg_restore`d the dump back in and
confirmed `SELECT count(*) FROM tenants` matched the pre-backup count — the
dump/restore cycle itself is proven; only the VPS-specific paths (cron,
Hostinger snapshots) are unverified.

## 9. Final smoke test checklist (run against the live deployment)

- [ ] Log in as `product_owner`, `admin`, and `pos_user` — each lands on
      the correct default route per `CLAUDE.md §5`.
- [ ] Complete a full POS sale: search an item, add to cart, apply a bill
      discount, finalize — server-recalculated total matches what the UI
      showed pre-submit.
- [ ] Print preview renders correctly for a thermal (80mm) profile.
- [ ] Print preview renders correctly for a dot-matrix profile.
- [ ] As `product_owner`, change a tenant's plan (e.g. Lite → Pro) and
      confirm that tenant's `admin` immediately sees the newly-unlocked
      dashboard/report features on next page load (no redeploy needed).
- [ ] Drop stock on an item below its reorder level and confirm a
      low-stock notification appears within one scheduler interval (15 min).
- [ ] Export a sales report (CSV, Pro/Pro Max tenant) and confirm the
      totals match what the dashboard shows for the same date range.

This checklist requires a live deployment to actually execute — it has not
been run against a real Hostinger VPS in this environment. Everything
upstream of it (image builds, compose config, migrations, the app's own
test suite) has been verified locally as documented in the sections above.
