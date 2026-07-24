#!/usr/bin/env bash
# Redeploys StoreMate TN on the Hostinger VPS. Run this ON THE VPS itself
# (via CI's SSH step, or manually over an SSH session) — not on the Windows
# dev machine. See docs/DEPLOYMENT.md for the one-time server setup this
# assumes is already done (Docker installed, repo cloned, .env in place,
# TLS certs already issued).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Pulling latest main"
git fetch origin main
git reset --hard origin/main

echo "==> Backing up the database before touching anything"
bash scripts/backup_db.sh

echo "==> Rebuilding and restarting the stack"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

echo "==> Applying database migrations"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend alembic upgrade head

echo "==> Pruning old images to keep disk usage sane"
docker image prune -f

echo "==> Deploy complete. Recent backend logs:"
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=30 backend
