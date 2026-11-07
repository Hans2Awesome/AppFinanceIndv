"""Tests for Google identity persistence and migration v6."""

from __future__ import annotations

import sqlite3

import pytest

from finance_core.db.categories import list_categories
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.db.users import (
    create_google_user,
    create_mobile_user,
    get_user_by_google_sub,
    link_google_identity,
    link_telegram_account,
)


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def test_google_sub_column_and_partial_unique_index_exist() -> None:
    connection = setup_connection()

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
    assert "google_sub" in columns

    indexes = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        ("idx_users_google_sub",),
    ).fetchall()
    assert len(indexes) == 1
    assert "WHERE google_sub IS NOT NULL" in indexes[0]["sql"]


def test_v5_database_upgrades_to_google_identity_in_place() -> None:
    connection = setup_connection()

    # Recreate the v5 state: no column, no partial index, no v6 record.
    connection.execute("DROP INDEX IF EXISTS idx_users_google_sub")
    connection.execute("ALTER TABLE users DROP COLUMN google_sub")
    connection.execute("DELETE FROM schema_migrations WHERE version = 6")

    init_db(connection)

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
    assert "google_sub" in columns
    versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations")]
    assert 6 in versions


def test_multiple_null_google_subjects_are_allowed_but_duplicates_are_not() -> None:
    connection = setup_connection()
    create_mobile_user(connection, email="one@example.com", password_hash="x")
    create_mobile_user(connection, email="two@example.com", password_hash="x")

    first = create_google_user(connection, google_sub="sub-1", email="a@example.com")
    with pytest.raises(sqlite3.IntegrityError):
        create_google_user(connection, google_sub="sub-1", email="b@example.com")

    assert get_user_by_google_sub(connection, "sub-1") == first


def test_google_user_has_no_password_and_gets_default_categories() -> None:
    connection = setup_connection()
    user = create_google_user(
        connection,
        google_sub="google-sub-123",
        email="User@Example.com",
        first_name="Hans",
    )

    assert user.email == "user@example.com"
    assert user.password_hash is None
    assert user.google_linked is True
    assert user.has_password is False
    assert len(list_categories(connection, user.id)) > 0


def test_link_google_identity_only_fills_an_empty_slot() -> None:
    connection = setup_connection()
    user = create_mobile_user(connection, email="owner@example.com", password_hash="hash")

    linked = link_google_identity(connection, user_id=user.id, google_sub="sub-owner")
    assert linked is not None and linked.google_sub == "sub-owner"

    same = link_google_identity(connection, user_id=user.id, google_sub="sub-owner")
    assert same is not None and same.google_sub == "sub-owner"

    different = link_google_identity(connection, user_id=user.id, google_sub="sub-other")
    assert different is not None and different.google_sub == "sub-owner"


def test_telegram_merge_refuses_a_bot_row_that_owns_a_google_identity() -> None:
    connection = setup_connection()
    owner = create_mobile_user(connection, email="owner@example.com", password_hash="hash")

    connection.execute(
        "INSERT INTO users (telegram_user_id, google_sub, first_name) VALUES (?, ?, ?)",
        (9001, "sub-bot", "Bot"),
    )
    bot = connection.execute(
        "SELECT id FROM users WHERE telegram_user_id = ?", (9001,)
    ).fetchone()

    with pytest.raises(ValueError, match="akun lain"):
        link_telegram_account(connection, user_id=owner.id, telegram_user_id=9001)

    assert bot is not None