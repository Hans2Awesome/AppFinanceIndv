"""Copy the SQLite database into PostgreSQL (Supabase).

Usage:
    python scripts/migrate_sqlite_to_postgres.py --database-url "$DATABASE_URL"
    python scripts/migrate_sqlite_to_postgres.py --sqlite bot04.sqlite3 --dry-run

The target schema is created first, then every table is copied with its
original ids inside one transaction. The script is safe to re-run: existing ids
are skipped, so it never duplicates rows. Nothing is written back to SQLite.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from finance_core.db.connection import close_pools, connect_url, transaction  # noqa: E402
from finance_core.db.migrations import run_migrations  # noqa: E402

# Parent tables first so foreign keys always find their rows.
TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "users",
        (
            "id",
            "telegram_user_id",
            "email",
            "password_hash",
            "first_name",
            "username",
            "timezone",
            "currency",
            "token_version",
            "created_at",
        ),
    ),
    ("categories", ("id", "user_id", "type", "name", "aliases", "is_default")),
    (
        "transactions",
        (
            "id",
            "user_id",
            "type",
            "category_id",
            "amount",
            "note",
            "asset_name",
            "transaction_date",
            "source_key",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "debts",
        (
            "id",
            "user_id",
            "type",
            "person_name",
            "total_amount",
            "paid_amount",
            "note",
            "due_date",
            "status",
            "cash_synced",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "debt_payments",
        ("id", "debt_id", "amount", "note", "payment_date", "created_at"),
    ),
    (
        "recurring_transactions",
        (
            "id",
            "user_id",
            "type",
            "category_id",
            "amount",
            "note",
            "asset_name",
            "frequency",
            "day_of_week",
            "day_of_month",
            "start_date",
            "next_run_date",
            "last_run_date",
            "is_active",
            "created_at",
            "updated_at",
        ),
    ),
)


def _sqlite_columns(source: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in source.execute(f"PRAGMA table_info({table})").fetchall()}


def _copy_table(
    source: sqlite3.Connection,
    target,
    table: str,
    columns: tuple[str, ...],
) -> int:
    available = _sqlite_columns(source, table)
    selected = tuple(column for column in columns if column in available)
    if not selected:
        return 0

    rows = source.execute(
        f"SELECT {', '.join(selected)} FROM {table} ORDER BY id"
    ).fetchall()
    if not rows:
        return 0

    placeholders = ", ".join("?" for _ in selected)
    target.executemany(
        f"""
        INSERT INTO {table} ({', '.join(selected)})
        VALUES ({placeholders})
        ON CONFLICT (id) DO NOTHING
        """,
        [tuple(row) for row in rows],
    )
    return len(rows)


def _reset_sequence(target, table: str) -> None:
    target.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table}', 'id'),
            GREATEST(COALESCE(MAX(id), 1), 1),
            COALESCE(MAX(id), 0) > 0
        )
        FROM {table}
        """
    )


def _table_exists(source: sqlite3.Connection, table: str) -> bool:
    return (
        source.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )


def migrate(sqlite_path: Path, database_url: str, *, dry_run: bool = False) -> int:
    """Copy every table and return the number of rows written."""

    if not sqlite_path.exists():
        raise SystemExit(f"SQLite database not found: {sqlite_path}")

    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row

    # Tabel baru (misal telegram_link_codes) belum ada di database SQLite lama.
    # Lewati, karena tabel itu memang dibuat oleh migrasi PostgreSQL, bukan data.
    tables = [(table, columns) for table, columns in TABLES if _table_exists(source, table)]

    target = connect_url(database_url)
    try:
        version = run_migrations(target)
        print(f"PostgreSQL schema version: {version}")

        if dry_run:
            for table, _ in tables:
                count = source.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"{table}: {count} row(s) would be copied")
            return 0

        copied = 0
        with transaction(target):
            for table, columns in tables:
                rows = _copy_table(source, target, table, columns)
                _reset_sequence(target, table)
                copied += rows
                print(f"{table}: {rows} row(s) copied")

        for table, _ in tables:
            sqlite_count = source.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            target_count = target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            status = "ok" if sqlite_count == target_count else "MISMATCH"
            print(f"verify {table}: sqlite={sqlite_count} postgres={target_count} {status}")
            if status != "ok":
                raise SystemExit(f"Row count mismatch for {table}")

        return copied
    finally:
        target.close()
        close_pools()
        source.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy the SQLite database into PostgreSQL")
    parser.add_argument("--sqlite", default="bot04.sqlite3", help="Path to the SQLite file")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="PostgreSQL connection URL (defaults to DATABASE_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only create the schema and report row counts",
    )
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("Set DATABASE_URL or pass --database-url.")

    copied = migrate(Path(args.sqlite), args.database_url, dry_run=args.dry_run)
    if not args.dry_run:
        print(f"Done. {copied} row(s) copied.")


if __name__ == "__main__":
    main()