#!/usr/bin/env bash
# Dumps the KOTMate TN Postgres database to ./backups/, pruning anything
# older than RETENTION_DAYS. Run on the VPS; scripts/deploy.sh already calls
# this before every redeploy. For a standing daily backup independent of
# deploys, add a crontab entry (see docs/DEPLOYMENT.md).
set -euo pipefail

cd "$(dirname "$0")/.."

# docker compose reads .env itself for the compose-file ${VAR} substitutions
# below, but this script's own pg_dump command also needs POSTGRES_USER/
# POSTGRES_DB directly in the shell — source it explicitly.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="./backups"
BACKUP_FILE="${BACKUP_DIR}/kotmate_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.traefik.yml)

echo "==> Dumping database to ${BACKUP_FILE}"
docker compose "${COMPOSE_FILES[@]}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-kotmate}" -d "${POSTGRES_DB:-kotmate}" -Fc \
  > "$BACKUP_FILE"

echo "==> Pruning backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -name 'kotmate_*.dump' -mtime "+${RETENTION_DAYS}" -delete

echo "==> Backup complete: ${BACKUP_FILE}"
