#!/usr/bin/env bash
# Weekly PostgreSQL/Supabase backup for the Finance app.
#
# Usage:
#   DATABASE_URL="postgresql://..." ./scripts/backup_postgres.sh
#   DIRECT_DATABASE_URL="postgresql://...:5432/..." ./scripts/backup_postgres.sh
#   BACKUP_DIR=/var/backups/finance RETENTION_DAYS=30 ./scripts/backup_postgres.sh
#
# Writes a gzip-compressed pg_dump into BACKUP_DIR and removes dumps older than
# RETENTION_DAYS. Exit code is non-zero when the dump fails or produces an empty
# archive, so cron can report the failure.
#
# Port matters: the API and bot use the transaction pooler (port 6543), but
# pg_dump needs a single session for a consistent snapshot and table locks. Set
# DIRECT_DATABASE_URL (port 5432) and this script prefers it over DATABASE_URL.
#
# Cron example (every Sunday at 03:00):
#   0 3 * * 0 DATABASE_URL="postgresql://..." DIRECT_DATABASE_URL="postgresql://...:5432/..." \
#       /path/to/scripts/backup_postgres.sh >> /var/log/finance-backup.log 2>&1

set -euo pipefail

BACKUP_URL="${DIRECT_DATABASE_URL:-${DATABASE_URL:-}}"
if [ -z "$BACKUP_URL" ]; then
    echo "DATABASE_URL (or DIRECT_DATABASE_URL) is required." >&2
    exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "pg_dump not found. Install the PostgreSQL client package." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
target="${BACKUP_DIR}/finance_$(date +%F).sql.gz"
partial="${target}.part"

# Write to a temp file first, so a failed dump never leaves a half-written
# archive under the final name.
cleanup() {
    rm -f "$partial"
}
trap cleanup EXIT

# --no-owner keeps the dump restorable into a different role or project.
if ! pg_dump "$BACKUP_URL" --no-owner --format=plain | gzip > "$partial"; then
    echo "Backup failed: pg_dump returned a non-zero exit code." >&2
    exit 1
fi

# gzip always emits a valid ~20 byte header/trailer, so a non-zero size alone
# does not prove the dump contains data. Require real SQL output as well.
# wc -c reads the stream to EOF, so gzip never gets SIGPIPE even when the dump
# exceeds the 64 KB kernel pipe buffer (grep -q . would exit early and kill
# gzip with exit 141 under `set -o pipefail`).
if [ ! -s "$partial" ] || test "$(gzip -dc "$partial" | wc -c)" -le 0; then
    echo "Backup failed: dump is empty." >&2
    exit 1
fi

mv "$partial" "$target"
echo "Backup written: $target"

find "$BACKUP_DIR" -name 'finance_*.sql.gz' -type f -mtime "+${RETENTION_DAYS}" -delete
echo "Removed backups older than ${RETENTION_DAYS} day(s)."
