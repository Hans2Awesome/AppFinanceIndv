"""Tests for Bot04 user repository."""

from __future__ import annotations

import sqlite3

from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.db.users import get_or_create_user


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def test_get_or_create_user_inserts_new_user() -> None:
    connection = setup_connection()

    user = get_or_create_user(
        connection,
        telegram_user_id=796529359,
        first_name="Hans",
        username="hans2awesome",
        timezone="Asia/Jakarta",
        currency="IDR",
    )

    assert user.id == 1
    assert user.telegram_user_id == 796529359
    assert user.first_name == "Hans"
    assert user.username == "hans2awesome"
    assert user.timezone == "Asia/Jakarta"
    assert user.currency == "IDR"
    assert user.email is None

    row_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert row_count == 1


def test_get_or_create_user_returns_existing_user_without_duplicate_insert() -> None:
    connection = setup_connection()

    first_user = get_or_create_user(
        connection,
        telegram_user_id=796529359,
        first_name="Hans",
        username="hans2awesome",
        timezone="Asia/Jakarta",
        currency="IDR",
    )
    second_user = get_or_create_user(
        connection,
        telegram_user_id=796529359,
        first_name="Changed Name",
        username="changed_username",
        timezone="UTC",
        currency="USD",
    )

    assert second_user == first_user
    row_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert row_count == 1
