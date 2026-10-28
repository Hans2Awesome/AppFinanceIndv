"""Tests for Bot04 SQLite schema initialization."""

from __future__ import annotations

import sqlite3

import pytest

from finance_core.db.connection import connect
from finance_core.db.migrations import init_db


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def test_init_db_creates_core_tables() -> None:
    connection = connect(":memory:")

    init_db(connection)

    assert table_names(connection) == {
        "users",
        "categories",
        "transactions",
        "debts",
        "debt_payments",
        "schema_migrations",
    }


def test_init_db_creates_expected_columns() -> None:
    connection = connect(":memory:")

    init_db(connection)

    assert column_names(connection, "users") == {
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
    }
    assert column_names(connection, "categories") == {
        "id",
        "user_id",
        "type",
        "name",
        "aliases",
        "is_default",
    }
    assert column_names(connection, "transactions") == {
        "id",
        "user_id",
        "type",
        "category_id",
        "amount",
        "note",
        "asset_name",
        "transaction_date",
        "created_at",
        "updated_at",
    }


def test_init_db_creates_query_indexes() -> None:
    connection = connect(":memory:")

    init_db(connection)

    index_rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"
    ).fetchall()
    index_names = {row[0] for row in index_rows}

    assert {
        "idx_transactions_user_date",
        "idx_categories_user_type",
        "idx_debts_user_status",
        "idx_debt_payments_debt",
    } <= index_names


def test_init_db_is_idempotent_and_records_version() -> None:
    connection = connect(":memory:")

    init_db(connection)
    init_db(connection)

    versions = connection.execute("SELECT version FROM schema_migrations").fetchall()

    assert [row[0] for row in versions] == [1, 2]


def test_users_telegram_user_id_must_be_unique() -> None:
    connection = connect(":memory:")
    init_db(connection)

    connection.execute(
        """
        INSERT INTO users (telegram_user_id, first_name, username, timezone, currency)
        VALUES (?, ?, ?, ?, ?)
        """,
        (796529359, "Hans", "hans", "Asia/Jakarta", "IDR"),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO users (telegram_user_id, first_name, username, timezone, currency)
            VALUES (?, ?, ?, ?, ?)
            """,
            (796529359, "Hans Duplicate", "hans2", "Asia/Jakarta", "IDR"),
        )


def test_categories_are_unique_per_user_type_and_name() -> None:
    connection = connect(":memory:")
    init_db(connection)
    cursor = connection.execute(
        """
        INSERT INTO users (telegram_user_id, first_name, username, timezone, currency)
        VALUES (?, ?, ?, ?, ?)
        """,
        (1, "User", "user", "Asia/Jakarta", "IDR"),
    )
    user_id = cursor.lastrowid

    connection.execute(
        """
        INSERT INTO categories (user_id, type, name, aliases, is_default)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, "expense", "Makan", "makan,kopi", 1),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO categories (user_id, type, name, aliases, is_default)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, "expense", "Makan", "sarapan", 0),
        )


def test_schema_rejects_non_positive_transaction_amount() -> None:
    connection = connect(":memory:")
    init_db(connection)
    connection.execute(
        "INSERT INTO users (telegram_user_id, first_name) VALUES (?, ?)",
        (1, "Hans"),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO transactions (user_id, type, amount, transaction_date)
            VALUES (1, 'expense', 0, '2026-05-30')
            """
        )
