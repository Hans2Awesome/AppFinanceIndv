"""Tests for the schema hardening from the Supabase DBA review.

Each case pins one guard that only exists in the database, so a future edit
cannot quietly reopen the hole:

- no duplicate index on ``telegram_link_codes.code``
- ``UPDATE`` is validated on categories and debt payments
- ``users.email`` must be lowercase
- migrations are serialized with an advisory lock on PostgreSQL
"""

from __future__ import annotations

import sqlite3

import pytest

from finance_core.db.connection import connect
from finance_core.db.migrations import init_db


@pytest.fixture
def db() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def _index_names(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = ?",
        (table,),
    ).fetchall()
    return {row[0] for row in rows}


def _user_id(connection: sqlite3.Connection, email: str = "user@example.test") -> int:
    cursor = connection.execute(
        "INSERT INTO users (email, first_name) VALUES (?, ?)",
        (email, "User"),
    )
    return int(cursor.lastrowid)


def test_telegram_link_codes_has_no_duplicate_index_on_code(db) -> None:
    """``code TEXT UNIQUE`` already provides an index for the lookup."""

    assert "idx_telegram_link_codes_code" not in _index_names(db, "telegram_link_codes")
    assert "idx_telegram_link_codes_user" in _index_names(db, "telegram_link_codes")


def test_category_update_rejects_unknown_type(db) -> None:
    user_id = _user_id(db)
    cursor = db.execute(
        "INSERT INTO categories (user_id, type, name) VALUES (?, 'expense', 'Kopi')",
        (user_id,),
    )
    category_id = int(cursor.lastrowid)

    with pytest.raises(sqlite3.IntegrityError, match="invalid category row"):
        db.execute(
            "UPDATE categories SET type = 'hutang' WHERE id = ?",
            (category_id,),
        )


def test_debt_payment_update_rejects_non_positive_amount(db) -> None:
    user_id = _user_id(db)
    cursor = db.execute(
        """
        INSERT INTO debts (user_id, type, person_name, total_amount)
        VALUES (?, 'debt', 'Budi', 500000)
        """,
        (user_id,),
    )
    debt_id = int(cursor.lastrowid)
    payment = db.execute(
        """
        INSERT INTO debt_payments (debt_id, amount, payment_date)
        VALUES (?, 100000, '2026-11-01')
        """,
        (debt_id,),
    )
    payment_id = int(payment.lastrowid)

    with pytest.raises(sqlite3.IntegrityError, match="invalid debt payment row"):
        db.execute(
            "UPDATE debt_payments SET amount = -50000 WHERE id = ?",
            (payment_id,),
        )


def test_user_email_must_be_lowercase_on_insert(db) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="email must be lowercase"):
        db.execute(
            "INSERT INTO users (email, first_name) VALUES ('User@Example.test', 'User')"
        )


def test_user_email_must_be_lowercase_on_update(db) -> None:
    user_id = _user_id(db)

    with pytest.raises(sqlite3.IntegrityError, match="email must be lowercase"):
        db.execute(
            "UPDATE users SET email = 'Upper@Example.test' WHERE id = ?",
            (user_id,),
        )


def test_bot_user_without_email_is_still_allowed(db) -> None:
    """The lowercase guard must not turn ``email`` into a required column."""

    db.execute(
        """
        INSERT INTO users (telegram_user_id, first_name) VALUES (?, ?)
        """,
        (796529359, "Hans"),
    )

    row = db.execute("SELECT email FROM users WHERE telegram_user_id = ?", (796529359,)).fetchone()
    assert row["email"] is None


def test_postgres_migrations_take_an_advisory_lock() -> None:
    """The lock is what stops two workers from racing on DDL at startup."""

    from finance_core.db.postgres_schema import _POSTGRES_MIGRATIONS

    assert sorted(_POSTGRES_MIGRATIONS) == [1, 2, 3, 4, 5, 6, 7, 8]

    import inspect

    from finance_core.db.postgres_schema import run_postgres_migrations

    source = inspect.getsource(run_postgres_migrations)
    assert "pg_advisory_xact_lock(4042026)" in source


def test_postgres_migration_5_enables_rls_on_every_table() -> None:
    from finance_core.db.postgres_schema import _MIGRATION_5, _RLS_TABLES

    statements = "\n".join(_MIGRATION_5)

    for table in _RLS_TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in statements

    assert len(_RLS_TABLES) == 7
