#!/usr/bin/env bash
# Redeploys StoreMate TN on the Hostinger VPS. Run this ON THE VPS itself
# (via CI's SSH step, or manually over an SSH session) — not on the Windows
# dev machine. See docs/DEPLOYMENT.md for the one-time server setup this
# assumes is already done (Docker installed, repo cloned, .env in place).
#
# TRAEFIK_MODE=1 uses docker-compose.traefik.yml and only starts
# db/backend/frontend, for deploying alongside another Traefik-fronted
# stack that already owns ports 80/443 (see docs/DEPLOYMENT.md §4b) — this
# is the mode actually used on the current VPS (n8n owns 80/443 via
# Traefik). Leave TRAEFIK_MODE unset for the standalone nginx+certbot path.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Pulling latest main"
git fetch origin main
git reset --hard origin/main

echo "==> Backing up the database before touching anything"
bash scripts/backup_db.sh

if [ "${TRAEFIK_MODE:-0}" = "1" ]; then
  COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.traefik.yml)
  SERVICES=(db backend frontend)
else
  COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml)
  SERVICES=()
fi

echo "==> Rebuilding and restarting the stack"
docker compose "${COMPOSE_FILES[@]}" up -d --build "${SERVICES[@]}"

echo "==> Applying database migrations"
docker compose "${COMPOSE_FILES[@]}" exec -T backend alembic upgrade head

echo "==> Pruning old images to keep disk usage sane"
docker image prune -f

echo "==> Deploy complete. Recent backend logs:"
docker compose "${COMPOSE_FILES[@]}" logs --tail=30 backend
