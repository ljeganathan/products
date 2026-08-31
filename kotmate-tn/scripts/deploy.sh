#!/usr/bin/env bash
# Redeploys KOTMate TN on the Hostinger VPS. Run this ON THE VPS itself (via
# CI's SSH step, or manually over an SSH session) — not on the Windows dev
# machine. See docs/DEPLOYMENT.md for the one-time server setup this assumes
# is already done (Docker installed, repo cloned, .env in place).
#
# Always deploys in Traefik co-location mode (docker-compose.traefik.yml,
# only starting postgres/backend/nginx/landing) — this VPS shares host ports
# 80/443 with an existing n8n + Traefik stack, which storemate-tn already
# deploys alongside the same way (see docs/DEPLOYMENT.md). `landing` is the
# kotmatetn.in marketing site — a separate static container with no
# dependency on postgres/backend (see docs/LANDING_PAGE.md).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Pulling latest main"
git fetch origin main
git reset --hard origin/main

echo "==> Backing up the database before touching anything"
bash scripts/backup_db.sh

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.traefik.yml)

echo "==> Rebuilding and restarting the stack"
docker compose "${COMPOSE_FILES[@]}" up -d --build postgres backend nginx landing

echo "==> Applying database migrations"
docker compose "${COMPOSE_FILES[@]}" exec -T backend alembic upgrade head

echo "==> Pruning old images to keep disk usage sane"
docker image prune -f

echo "==> Deploy complete. Recent backend logs:"
docker compose "${COMPOSE_FILES[@]}" logs --tail=30 backend
