#!/usr/bin/env bash
# Nightly Postgres backup. Cron example:
#   0 3 * * * BACKUP_DIR=/var/backups/herald /path/to/scripts/backup_db.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
COMPOSE_DB_SERVICE="${COMPOSE_DB_SERVICE:-db}"

# cron runs with cwd=$HOME; docker compose needs the repo root to find the compose file
cd "$(dirname "$0")/.."

mkdir -p "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/herald-$stamp.sql.gz"
docker compose exec -T "$COMPOSE_DB_SERVICE" pg_dump -U herald herald \
  | gzip > "$target.tmp"
mv "$target.tmp" "$target"
find "$BACKUP_DIR" -name 'herald-*.sql.gz' -mtime "+$KEEP_DAYS" -delete
find "$BACKUP_DIR" -name '*.sql.gz.tmp' -mtime +1 -delete
echo "backup written: $target"
