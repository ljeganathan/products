#!/usr/bin/env bash
# Dumps the production Postgres database to a timestamped, restorable file.
# Run on the Hostinger VPS — either manually, from scripts/deploy.sh before
# every redeploy, or via cron (see docs/DEPLOYMENT.md §Backups for the
# crontab line). Keeps the last 14 daily backups and prunes older ones.
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$BACKUP_DIR/storemate_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

# -Fc = pg_dump's custom format: compressed and required for pg_restore
# (a plain .sql dump would also work but loses parallel-restore and
# selective-table-restore ability).
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  pg_dump -U "${POSTGRES_USER:-storemate}" -d "${POSTGRES_DB:-storemate}" -Fc \
  > "$OUT_FILE"

echo "Backup written to $OUT_FILE ($(du -h "$OUT_FILE" | cut -f1))"

find "$BACKUP_DIR" -name 'storemate_*.dump' -mtime +"$RETENTION_DAYS" -delete
