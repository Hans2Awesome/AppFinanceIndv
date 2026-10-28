"""Tests for the versioned schema migrations."""

from __future__ import annotations

import sqlite3

from finance_core.db.connection import connect
from finance_core.db.migrations import SCHEMA_VERSION, current_version, run_migrations


def _legacy_bot_database(path: str) -> sqlite3.Connection:
    """Recreate the original bot-only schema, including the dead wallets table."""

    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER NOT NULL UNIQUE,
            first_name TEXT,
            username TEXT,
            timezone TEXT NOT NULL DEFAULT 'Asia/Jakarta',
            currency TEXT NOT NULL DEFAULT 'IDR',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            aliases TEXT NOT NULL DEFAULT '',
            is_default INTEGER NOT NULL DEFAULT 0,
            UNIQUE (user_id, type, name)
        );
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            category_id INTEGER,
            amount INTEGER NOT NULL,
            note TEXT,
            asset_name TEXT,
            transaction_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            balance INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO users (telegram_user_id, first_name) VALUES (123, 'Legacy');
        """
    )
    connection.commit()
    return connection


def test_legacy_bot_database_is_upgraded_in_place(tmp_path) -> None:
    path = str(tmp_path / "legacy.sqlite3")
    legacy = _legacy_bot_database(path)
    legacy.close()

    connection = connect(path)
    try:
        version = run_migrations(connection)

        assert version == SCHEMA_VERSION

        user_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(users)")
        }
        assert {"email", "password_hash", "token_version"} <= user_columns

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "wallets" not in tables
        assert {"debts", "debt_payments", "schema_migrations"} <= tables

        kept_users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert kept_users == 1
    finally:
        connection.close()


def test_migrations_are_idempotent(tmp_path) -> None:
    connection = connect(str(tmp_path / "fresh.sqlite3"))
    try:
        run_migrations(connection)
        run_migrations(connection)

        rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
        assert [row[0] for row in rows] == list(range(1, SCHEMA_VERSION + 1))
        assert current_version(connection) == SCHEMA_VERSION
    finally:
        connection.close()
