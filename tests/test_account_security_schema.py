"""Schema tests for the password reset request table (migration 7).

The table stores only a hash of the reset code, so a database dump never leaks a
usable code. ``request_id`` is the opaque primary key the client holds; the
plaintext code never reaches the database.
"""

from __future__ import annotations

import sqlite3

from finance_core.db.connection import connect
from finance_core.db.migrations import SCHEMA_VERSION, current_version, init_db, run_migrations

REQUIRED_COLUMNS = {
    "request_id",
    "user_id",
    "code_hash",
    "expires_at",
    "attempts",
    "token_version",
}


def _column_info(connection: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    return {row[1]: row for row in connection.execute(f"PRAGMA table_info({table})")}


def test_schema_version_is_eight() -> None:
    assert SCHEMA_VERSION == 8


def test_password_reset_requests_table_has_expected_columns() -> None:
    connection = connect(":memory:")
    init_db(connection)

    columns = set(_column_info(connection, "password_reset_requests"))
    assert REQUIRED_COLUMNS <= columns
    # No plaintext code is ever stored.
    assert "code" not in columns


def test_password_reset_requests_request_id_is_primary_key() -> None:
    connection = connect(":memory:")
    init_db(connection)

    info = _column_info(connection, "password_reset_requests")
    assert info["request_id"][5] == 1


def test_password_reset_requests_integer_columns() -> None:
    connection = connect(":memory:")
    init_db(connection)

    info = _column_info(connection, "password_reset_requests")
    for column in ("expires_at", "attempts", "token_version"):
        assert "INT" in (info[column][2] or "").upper(), column


def test_password_reset_requests_user_foreign_key_cascades() -> None:
    connection = connect(":memory:")
    init_db(connection)
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    cursor = connection.execute(
        "INSERT INTO users (email, first_name) VALUES (?, ?)",
        ("cascade@example.com", "Cascade"),
    )
    user_id = int(cursor.lastrowid)
    connection.execute(
        """
        INSERT INTO password_reset_requests
            (request_id, user_id, code_hash, expires_at, attempts, token_version)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("req-cascade", user_id, "hash", 100, 0, 0),
    )

    connection.execute("DELETE FROM users WHERE id = ?", (user_id,))

    remaining = connection.execute(
        "SELECT COUNT(*) FROM password_reset_requests WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]
    assert remaining == 0


def test_migrations_record_current_version_and_are_idempotent(tmp_path) -> None:
    connection = connect(str(tmp_path / "fresh.sqlite3"))
    try:
        run_migrations(connection)
        run_migrations(connection)

        versions = [
            row[0] for row in connection.execute("SELECT version FROM schema_migrations")
        ]
        assert versions == list(range(1, 9))
        assert current_version(connection) == 8
    finally:
        connection.close()


def test_postgres_migration_seven_creates_and_locks_the_reset_table() -> None:
    from finance_core.db.postgres_schema import _POSTGRES_MIGRATIONS

    assert 7 in _POSTGRES_MIGRATIONS
    statements = "\n".join(_POSTGRES_MIGRATIONS[7])

    assert "CREATE TABLE IF NOT EXISTS password_reset_requests" in statements
    assert "password_reset_requests ENABLE ROW LEVEL SECURITY" in statements
