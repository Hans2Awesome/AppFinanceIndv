"""Versioned SQLite schema migrations shared by the API and the Telegram bot.

The schema is applied once at process startup. Request handlers must never
create tables; ``run_migrations`` is idempotent and records each version in
``schema_migrations``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from .postgres_schema import run_postgres_migrations

SCHEMA_VERSION = 6


def _create_core_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            first_name TEXT,
            username TEXT,
            timezone TEXT NOT NULL DEFAULT 'Asia/Jakarta',
            currency TEXT NOT NULL DEFAULT 'IDR',
            token_version INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            aliases TEXT NOT NULL DEFAULT '',
            is_default INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (user_id, type, name)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            category_id INTEGER,
            amount INTEGER NOT NULL,
            note TEXT,
            asset_name TEXT,
            transaction_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            person_name TEXT NOT NULL,
            total_amount INTEGER NOT NULL,
            paid_amount INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS debt_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debt_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            note TEXT,
            payment_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (debt_id) REFERENCES debts(id) ON DELETE CASCADE
        );
        """
    )


def _add_missing_user_columns(connection: sqlite3.Connection) -> None:
    """Add auth columns to databases created by the original bot schema."""

    existing_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    if "email" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "password_hash" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")


def _archive_dead_wallets_table(connection: sqlite3.Connection) -> None:
    """Move the unused legacy ``wallets`` table aside instead of destroying it."""

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "wallets" in tables and "wallets_archive" not in tables:
        connection.execute("ALTER TABLE wallets RENAME TO wallets_archive")


def _create_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_transactions_user_date
            ON transactions (user_id, transaction_date, id);
        CREATE INDEX IF NOT EXISTS idx_transactions_user_type_date
            ON transactions (user_id, type, transaction_date, id);
        CREATE INDEX IF NOT EXISTS idx_categories_user_type
            ON categories (user_id, type);
        CREATE INDEX IF NOT EXISTS idx_debts_user_status
            ON debts (user_id, status);
        CREATE INDEX IF NOT EXISTS idx_debt_payments_debt
            ON debt_payments (debt_id, payment_date);
        """
    )


def _migration_1(connection: sqlite3.Connection) -> None:
    """Unified baseline schema for the API and the bot."""

    _create_core_tables(connection)
    _add_missing_user_columns(connection)
    _archive_dead_wallets_table(connection)
    _create_indexes(connection)


def _add_user_token_version(connection: sqlite3.Connection) -> None:
    """Add the token revocation counter to databases created before version 2."""

    existing_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    if "token_version" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"
        )


def _create_integrity_triggers(connection: sqlite3.Connection) -> None:
    """Reject invalid rows even when a caller bypasses the Pydantic schemas."""

    connection.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS trg_transactions_valid_insert
        BEFORE INSERT ON transactions
        WHEN NEW.amount <= 0
             OR NEW.type NOT IN ('income', 'expense', 'investment')
        BEGIN SELECT RAISE(ABORT, 'invalid transaction row'); END;

        CREATE TRIGGER IF NOT EXISTS trg_transactions_valid_update
        BEFORE UPDATE ON transactions
        WHEN NEW.amount <= 0
             OR NEW.type NOT IN ('income', 'expense', 'investment')
        BEGIN SELECT RAISE(ABORT, 'invalid transaction row'); END;

        CREATE TRIGGER IF NOT EXISTS trg_categories_valid_insert
        BEFORE INSERT ON categories
        WHEN NEW.type NOT IN ('income', 'expense', 'investment')
        BEGIN SELECT RAISE(ABORT, 'invalid category row'); END;

        CREATE TRIGGER IF NOT EXISTS trg_debts_valid_insert
        BEFORE INSERT ON debts
        WHEN NEW.type NOT IN ('debt', 'receivable')
             OR NEW.status NOT IN ('active', 'settled')
             OR NEW.total_amount <= 0
             OR NEW.paid_amount < 0
        BEGIN SELECT RAISE(ABORT, 'invalid debt row'); END;

        CREATE TRIGGER IF NOT EXISTS trg_debts_valid_update
        BEFORE UPDATE ON debts
        WHEN NEW.type NOT IN ('debt', 'receivable')
             OR NEW.status NOT IN ('active', 'settled')
             OR NEW.total_amount <= 0
             OR NEW.paid_amount < 0
             OR NEW.paid_amount > NEW.total_amount
        BEGIN SELECT RAISE(ABORT, 'invalid debt row'); END;

        CREATE TRIGGER IF NOT EXISTS trg_debt_payments_valid_insert
        BEFORE INSERT ON debt_payments
        WHEN NEW.amount <= 0
        BEGIN SELECT RAISE(ABORT, 'invalid debt payment row'); END;
        """
    )


def _migration_2(connection: sqlite3.Connection) -> None:
    """Token revocation counter plus database-level integrity checks."""

    _add_user_token_version(connection)
    _create_integrity_triggers(connection)


def _add_column_if_missing(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    """Add a column to an existing table, ignoring databases that already have it."""

    existing_columns = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing_columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _create_recurring_table(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS recurring_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            category_id INTEGER,
            amount INTEGER NOT NULL,
            note TEXT,
            asset_name TEXT,
            frequency TEXT NOT NULL,
            day_of_week INTEGER,
            day_of_month INTEGER,
            start_date TEXT NOT NULL,
            next_run_date TEXT NOT NULL,
            last_run_date TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_recurring_due
            ON recurring_transactions (is_active, next_run_date);
        CREATE INDEX IF NOT EXISTS idx_recurring_user
            ON recurring_transactions (user_id, is_active, next_run_date);

        CREATE TRIGGER IF NOT EXISTS trg_recurring_valid_insert
        BEFORE INSERT ON recurring_transactions
        WHEN NEW.type NOT IN ('income', 'expense', 'investment')
             OR NEW.amount <= 0
             OR NEW.frequency NOT IN ('weekly', 'monthly')
             OR NEW.is_active NOT IN (0, 1)
             OR (NEW.frequency = 'weekly'
                 AND (NEW.day_of_week IS NULL OR NEW.day_of_week < 0 OR NEW.day_of_week > 6))
             OR (NEW.frequency = 'monthly'
                 AND (NEW.day_of_month IS NULL OR NEW.day_of_month < 1 OR NEW.day_of_month > 31))
        BEGIN SELECT RAISE(ABORT, 'invalid recurring transaction row'); END;

        CREATE TRIGGER IF NOT EXISTS trg_recurring_valid_update
        BEFORE UPDATE ON recurring_transactions
        WHEN NEW.type NOT IN ('income', 'expense', 'investment')
             OR NEW.amount <= 0
             OR NEW.frequency NOT IN ('weekly', 'monthly')
             OR NEW.is_active NOT IN (0, 1)
             OR (NEW.frequency = 'weekly'
                 AND (NEW.day_of_week IS NULL OR NEW.day_of_week < 0 OR NEW.day_of_week > 6))
             OR (NEW.frequency = 'monthly'
                 AND (NEW.day_of_month IS NULL OR NEW.day_of_month < 1 OR NEW.day_of_month > 31))
        BEGIN SELECT RAISE(ABORT, 'invalid recurring transaction row'); END;
        """
    )


def _migration_3(connection: sqlite3.Connection) -> None:
    """Recurring schedules plus cash links for generated transactions and debts."""

    _create_recurring_table(connection)
    _add_column_if_missing(connection, "transactions", "source_key", "TEXT")
    _add_column_if_missing(connection, "debts", "cash_synced", "INTEGER NOT NULL DEFAULT 0")
    connection.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_source_key
            ON transactions (source_key)
            WHERE source_key IS NOT NULL;
        """
    )


def _create_telegram_link_codes_table(connection: sqlite3.Connection) -> None:
    """Kode tautan satu kali pakai untuk menghubungkan akun Mobile dengan Telegram."""

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS telegram_link_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            code TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_telegram_link_codes_code
            ON telegram_link_codes (code);
        CREATE INDEX IF NOT EXISTS idx_telegram_link_codes_user
            ON telegram_link_codes (user_id);
        """
    )


def _migration_4(connection: sqlite3.Connection) -> None:
    """Account linking between Mobile (email) and Telegram (telegram_user_id)."""

    _create_telegram_link_codes_table(connection)


def _migration_5(connection: sqlite3.Connection) -> None:
    """Guard the remaining UPDATE paths, lowercase email, drop a duplicate index.

    Mirrors the PostgreSQL migration of the same version so both dialects stay
    on one schema number.
    """

    # ``code`` UNIQUE already creates an index; the manual copy only doubled
    # write cost.
    connection.execute("DROP INDEX IF EXISTS idx_telegram_link_codes_code")

    connection.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS trg_categories_valid_update
        BEFORE UPDATE ON categories
        WHEN NEW.type NOT IN ('income', 'expense', 'investment')
        BEGIN SELECT RAISE(ABORT, 'invalid category row'); END;

        CREATE TRIGGER IF NOT EXISTS trg_debt_payments_valid_update
        BEFORE UPDATE ON debt_payments
        WHEN NEW.amount <= 0
        BEGIN SELECT RAISE(ABORT, 'invalid debt payment row'); END;

        CREATE TRIGGER IF NOT EXISTS trg_users_email_lower_insert
        BEFORE INSERT ON users
        WHEN NEW.email IS NOT NULL AND NEW.email <> lower(NEW.email)
        BEGIN SELECT RAISE(ABORT, 'email must be lowercase'); END;

        CREATE TRIGGER IF NOT EXISTS trg_users_email_lower_update
        BEFORE UPDATE ON users
        WHEN NEW.email IS NOT NULL AND NEW.email <> lower(NEW.email)
        BEGIN SELECT RAISE(ABORT, 'email must be lowercase'); END;
        """
    )


def _migration_6(connection: sqlite3.Connection) -> None:
    """Add the immutable Google subject used for Android sign-in.

    SQLite cannot add a UNIQUE column in place, so the column is plain and the
    uniqueness comes from a partial index that ignores bot-only users.
    """

    _add_column_if_missing(connection, "users", "google_sub", "TEXT")
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub
            ON users (google_sub)
            WHERE google_sub IS NOT NULL
        """
    )


_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migration_1,
    2: _migration_2,
    3: _migration_3,
    4: _migration_4,
    5: _migration_5,
    6: _migration_6,
}


def _ensure_version_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def run_migrations(connection: sqlite3.Connection) -> int:
    """Apply every pending migration and return the resulting schema version."""

    from .connection import is_postgres

    if is_postgres(connection):
        return run_postgres_migrations(connection)

    # WAL is a persistent database property, so it belongs to the startup path,
    # not to every request connection.
    connection.execute("PRAGMA journal_mode = WAL")
    _ensure_version_table(connection)
    applied = {
        row["version"] for row in connection.execute("SELECT version FROM schema_migrations")
    }

    for version in sorted(_MIGRATIONS):
        if version in applied:
            continue
        with connection:
            _MIGRATIONS[version](connection)
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )

    return current_version(connection)


def current_version(connection: sqlite3.Connection) -> int:
    """Return the highest applied schema version, or 0 for an empty database."""

    _ensure_version_table(connection)
    row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0] or 0)


def init_db(connection: sqlite3.Connection) -> None:
    """Backward-compatible alias used by callers and tests."""

    run_migrations(connection)