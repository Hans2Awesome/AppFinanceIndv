"""Tests for Bot04 default category seeding."""

from __future__ import annotations

import sqlite3

from finance_core.db.categories import seed_default_categories
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.db.users import get_or_create_user


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def category_rows(connection: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return connection.execute(
        """
        SELECT type, name, aliases, is_default
        FROM categories
        WHERE user_id = ?
        ORDER BY type, name
        """,
        (user_id,),
    ).fetchall()


def test_seed_default_categories_creates_income_expense_and_investment_defaults() -> None:
    connection = setup_connection()
    user = get_or_create_user(connection, telegram_user_id=796529359)

    seed_default_categories(connection, user.id)

    rows = category_rows(connection, user.id)
    category_keys = {(row["type"], row["name"]) for row in rows}

    assert len(rows) == 20
    assert category_keys == {
        ("income", "Gaji"),
        ("income", "Bonus"),
        ("income", "Freelance"),
        ("income", "Bisnis"),
        ("income", "Hadiah"),
        ("income", "Lainnya"),
        ("expense", "Makan & Minum"),
        ("expense", "Transportasi"),
        ("expense", "Belanja"),
        ("expense", "Tagihan"),
        ("expense", "Hiburan"),
        ("expense", "Kesehatan"),
        ("expense", "Pendidikan"),
        ("expense", "Lainnya"),
        ("investment", "Saham"),
        ("investment", "Crypto"),
        ("investment", "Reksadana"),
        ("investment", "Emas"),
        ("investment", "Deposito"),
        ("investment", "Lainnya"),
    }
    assert all(row["is_default"] == 1 for row in rows)


def test_seed_default_categories_stores_aliases_for_fast_text_parser() -> None:
    connection = setup_connection()
    user = get_or_create_user(connection, telegram_user_id=796529359)

    seed_default_categories(connection, user.id)

    aliases_by_key = {
        (row["type"], row["name"]): row["aliases"]
        for row in category_rows(connection, user.id)
    }
    assert aliases_by_key[("income", "Gaji")] == "gaji,salary"
    assert (
        aliases_by_key[("expense", "Makan & Minum")]
        == "makan,minum,kopi,sarapan,makan siang,makan malam"
    )
    assert aliases_by_key[("investment", "Crypto")] == (
        "crypto,kripto,btc,eth,bitcoin,ethereum"
    )


def test_seed_default_categories_is_idempotent_for_same_user() -> None:
    connection = setup_connection()
    user = get_or_create_user(connection, telegram_user_id=796529359)

    seed_default_categories(connection, user.id)
    seed_default_categories(connection, user.id)

    row_count = connection.execute(
        "SELECT COUNT(*) FROM categories WHERE user_id = ?",
        (user.id,),
    ).fetchone()[0]
    assert row_count == 20


def test_seed_default_categories_creates_separate_defaults_per_user() -> None:
    connection = setup_connection()
    first_user = get_or_create_user(connection, telegram_user_id=1)
    second_user = get_or_create_user(connection, telegram_user_id=2)

    seed_default_categories(connection, first_user.id)
    seed_default_categories(connection, second_user.id)

    first_count = connection.execute(
        "SELECT COUNT(*) FROM categories WHERE user_id = ?",
        (first_user.id,),
    ).fetchone()[0]
    second_count = connection.execute(
        "SELECT COUNT(*) FROM categories WHERE user_id = ?",
        (second_user.id,),
    ).fetchone()[0]

    assert first_count == 20
    assert second_count == 20
