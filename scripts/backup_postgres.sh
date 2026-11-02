#!/usr/bin/env bash
# Weekly PostgreSQL/Supabase backup for the Finance app.
#
# Usage:
#   DATABASE_URL="postgresql://..." ./scripts/backup_postgres.sh
#   BACKUP_DIR=/var/backups/finance RETENTION_DAYS=30 ./scripts/backup_postgres.sh
#
# Writes a gzip-compressed pg_dump into BACKUP_DIR and removes dumps older than
# RETENTION_DAYS. Exit code is non-zero when DATABASE_URL is missing, pg_dump
# fails, or the dump is empty, so cron can report the failure.
#
# Cron example (every Sunday at 03:00):
#   0 3 * * 0 DATABASE_URL="postgresql://..." /path/to/scripts/backup_postgres.sh

set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "pg_dump not found. Install the PostgreSQL client package." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
target="${BACKUP_DIR}/finance_$(date +%F).sql.gz"

# --no-owner keeps the dump restorable into a different role or project.
pg_dump "$DATABASE_URL" --no-owner --format=plain | gzip > "$target"

if [ ! -s "$target" ]; then
    echo "Backup failed: $target is empty." >&2
    exit 1
fi

echo "Backup written: $target"

find "$BACKUP_DIR" -name 'finance_*.sql.gz' -type f -mtime "+${RETENTION_DAYS}" -delete
echo "Removed backups older than ${RETENTION_DAYS} day(s)."
