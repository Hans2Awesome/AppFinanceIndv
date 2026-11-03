#!/usr/bin/env bash
# Copy the whole public schema from one PostgreSQL/Supabase project to another.
#
# Why a dump/restore instead of the SQLite migration script: the SQLite script
# reads from a SQLite file. To move Supabase -> Supabase you dump the source
# with pg_dump and restore into the target. pg_dump keeps ids, sequences, keys,
# indexes, triggers and defaults, so the result is byte-equivalent in structure
# and identical in data.
#
# Usage:
#   SOURCE_URL="postgresql://...:5432/postgres" \
#   TARGET_URL="postgresql://...:5432/postgres" \
#   ./scripts/copy_postgres_database.sh
#
#   SOURCE_URL=... TARGET_URL=... DRY_RUN=1 ./scripts/copy_postgres_database.sh
#
# Env:
#   SOURCE_URL   (required) session/direct DSN of the old project, port 5432
#   TARGET_URL   (required) session/direct DSN of the new project, port 5432
#   DUMP_DIR     where the temporary dump lives (default ./backups)
#   KEEP_DUMP=1  keep the dump file instead of deleting it
#   DRY_RUN=1    dump only, do not touch the target
#   FORCE=1      restore even if the target already has rows
#
# Both URLs must use port 5432. Transaction pooler (6543) cannot run a
# consistent dump: pg_dump needs one session and table locks.

set -euo pipefail

: "${SOURCE_URL:?SOURCE_URL is required (session/direct DSN, port 5432)}"
: "${TARGET_URL:?TARGET_URL is required (session/direct DSN, port 5432)}"
DUMP_DIR="${DUMP_DIR:-./backups}"
KEEP_DUMP="${KEEP_DUMP:-0}"
DRY_RUN="${DRY_RUN:-0}"
FORCE="${FORCE:-0}"

for command in pg_dump pg_restore psql; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "$command not found. Install the PostgreSQL client package." >&2
        exit 1
    fi
done

# A pooler URL would fail or produce an inconsistent snapshot. Catch it early
# with a clear message instead of a confusing pg_dump error.
case "$SOURCE_URL" in
    *:6543/*) echo "SOURCE_URL uses the transaction pooler (6543). Use port 5432." >&2; exit 1 ;;
esac
case "$TARGET_URL" in
    *:6543/*) echo "TARGET_URL uses the transaction pooler (6543). Use port 5432." >&2; exit 1 ;;
esac

if [ "$SOURCE_URL" = "$TARGET_URL" ]; then
    echo "SOURCE_URL and TARGET_URL are the same database. Refusing to run." >&2
    exit 1
fi

mkdir -p "$DUMP_DIR"
stamp="$(date +%Y-%m-%d_%H%M%S)"
dump_file="${DUMP_DIR}/move_${stamp}.dump"

cleanup() {
    rm -f "${dump_file}.toc" "${dump_file}.toc.filtered"
    if [ "$KEEP_DUMP" != "1" ] && [ "$DRY_RUN" != "1" ]; then
        rm -f "$dump_file"
    fi
}
trap cleanup EXIT

echo "==> Dumping source"
start=$(date +%s)
# --schema=public: Supabase keeps auth/storage/etc. in other schemas, and the
# app never touches them. Copying them would collide with the target's own
# Supabase-managed objects.
pg_dump "$SOURCE_URL" \
    --schema=public \
    --no-owner \
    --no-privileges \
    --format=custom \
    --file="$dump_file"

dump_seconds=$(( $(date +%s) - start ))
dump_size=$(du -h "$dump_file" | cut -f1)
echo "    dump: $dump_file ($dump_size, ${dump_seconds}s)"

if [ ! -s "$dump_file" ]; then
    echo "Dump is empty. Aborting." >&2
    exit 1
fi

# pg_restore --list is the cheapest integrity check: it parses the archive
# without touching any database.
if ! pg_restore --list "$dump_file" >/dev/null; then
    echo "Dump is unreadable. Aborting." >&2
    exit 1
fi

if [ "$DRY_RUN" = "1" ]; then
    echo "==> DRY_RUN: dump verified, target untouched"
    exit 0
fi

if [ "$FORCE" != "1" ]; then
    existing=$(psql "$TARGET_URL" -tAc \
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null || echo "0")
    if [ "${existing:-0}" != "0" ]; then
        echo "Target already has $existing table(s) in schema public." >&2
        echo "Restoring on top can duplicate data. Re-run with FORCE=1 if you are sure." >&2
        exit 1
    fi
fi

echo "==> Restoring into target"
start=$(date +%s)

# A fresh Supabase project already ships a `public` schema, so the dump's own
# `SCHEMA - public` entry fails with "schema public already exists". Filter just
# that entry (and its comment) out of the restore list; every table, index,
# sequence, key and trigger in the dump is kept.
restore_list="${dump_file}.toc"
if ! pg_restore --list "$dump_file" > "$restore_list"; then
    echo "Could not read the dump's table of contents." >&2
    exit 1
fi
grep -vE 'SCHEMA - public |COMMENT - SCHEMA public ' "$restore_list" > "${restore_list}.filtered"
mv "${restore_list}.filtered" "$restore_list"

# --use-list: restore only the filtered entries.
# --single-transaction: all-or-nothing. A failure halfway leaves the target
# empty instead of half-populated.
# --no-owner/--no-privileges: the target role is different from the source.
set +e
pg_restore \
    --dbname="$TARGET_URL" \
    --no-owner \
    --no-privileges \
    --single-transaction \
    --exit-on-error \
    --use-list="$restore_list" \
    "$dump_file"
restore_status=$?
set -e
restore_seconds=$(( $(date +%s) - start ))

if [ "$restore_status" -ne 0 ]; then
    echo "Restore failed (exit $restore_status). Target was rolled back." >&2
    exit "$restore_status"
fi
echo "    restore: ${restore_seconds}s"

echo "==> Verifying row counts per table"
echo "source / target"
psql "$SOURCE_URL" -tAc \
    "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename" \
    > /tmp/copy_db_tables.$$

status=0
while read -r table; do
    [ -z "$table" ] && continue
    source_count=$(psql "$SOURCE_URL" -tAc "SELECT count(*) FROM public.\"$table\"")
    target_count=$(psql "$TARGET_URL" -tAc "SELECT count(*) FROM public.\"$table\"")
    if [ "$source_count" = "$target_count" ]; then
        printf "  %-28s %6s / %6s ok\n" "$table" "$source_count" "$target_count"
    else
        printf "  %-28s %6s / %6s MISMATCH\n" "$table" "$source_count" "$target_count"
        status=1
    fi
done < /tmp/copy_db_tables.$$
rm -f /tmp/copy_db_tables.$$

if [ "$status" -ne 0 ]; then
    echo "Row counts differ. Investigate before switching the app over." >&2
    exit 1
fi

echo
echo "Done. Next steps:"
echo "  1. Point DATABASE_URL at the target pooler (port 6543) in .env"
echo "  2. Start the API, then the bot"
echo "  3. Log in and check history, reports and debts"
