"""Tests for saving confirmed transaction previews."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from finance_core.db.categories import seed_default_categories
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.db.users import get_or_create_user
from finance_core.services.quick_input_parser import QuickInputResult
from finance_core.services.transaction_service import (
    SavedTransactionSummary,
    TransactionServiceError,
    save_confirmed_transaction,
)


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def setup_user(connection: sqlite3.Connection, telegram_user_id: int = 796529359) -> int:
    user = get_or_create_user(connection, telegram_user_id=telegram_user_id)
    seed_default_categories(connection, user.id)
    return user.id


def preview(
    *,
    type: str = "expense",
    category_name: str = "Makan & Minum",
    amount: int = 25000,
    note: str = "kopi pagi",
    asset_name: str | None = None,
    transaction_date: date = date(2026, 5, 30),
) -> QuickInputResult:
    return QuickInputResult(
        type=type,
        category_name=category_name,
        amount=amount,
        note=note,
        asset_name=asset_name,
        transaction_date=transaction_date,
        confidence=1.0,
        needs_review=False,
        original_text="makan 25000 kopi pagi",
        error=None,
    )


def test_save_confirmed_transaction_saves_preview_to_matching_user_category() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)

    summary = save_confirmed_transaction(connection, user_id=user_id, preview=preview())

    assert summary == SavedTransactionSummary(
        id=1,
        type="expense",
        category_name="Makan & Minum",
        amount=25000,
        note="kopi pagi",
        asset_name=None,
        transaction_date="2026-05-30",
    )
    row = connection.execute(
        """
        SELECT t.type, c.name, t.amount, t.note, t.asset_name, t.transaction_date
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE t.user_id = ?
        """,
        (user_id,),
    ).fetchone()
    assert tuple(row) == ("expense", "Makan & Minum", 25000, "kopi pagi", None, "2026-05-30")


def test_save_confirmed_transaction_saves_investment_asset() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)

    summary = save_confirmed_transaction(
        connection,
        user_id=user_id,
        preview=preview(
            type="investment",
            category_name="Crypto",
            amount=100000,
            note="dca mingguan",
            asset_name="BTC",
        ),
    )

    assert summary.type == "investment"
    assert summary.category_name == "Crypto"
    assert summary.asset_name == "BTC"


def test_save_confirmed_transaction_does_not_save_when_category_is_invalid() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)

    with pytest.raises(TransactionServiceError, match="Kategori tidak valid"):
        save_confirmed_transaction(
            connection,
            user_id=user_id,
            preview=preview(category_name="Tidak Ada"),
        )

    row_count = connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert row_count == 0


def test_save_confirmed_transaction_does_not_use_other_users_category() -> None:
    connection = setup_connection()
    first_user_id = setup_user(connection, telegram_user_id=1)
    second_user = get_or_create_user(connection, telegram_user_id=2)

    with pytest.raises(TransactionServiceError, match="Kategori tidak valid"):
        save_confirmed_transaction(connection, user_id=second_user.id, preview=preview())

    first_count = connection.execute(
        "SELECT COUNT(*) FROM transactions WHERE user_id = ?",
        (first_user_id,),
    ).fetchone()[0]
    second_count = connection.execute(
        "SELECT COUNT(*) FROM transactions WHERE user_id = ?",
        (second_user.id,),
    ).fetchone()[0]

    assert first_count == 0
    assert second_count == 0


def test_save_confirmed_transaction_rejects_error_preview() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    error_preview = QuickInputResult(
        type=None,
        category_name=None,
        amount=None,
        note="",
        asset_name=None,
        transaction_date=None,
        confidence=0.0,
        needs_review=True,
        original_text="",
        error="Nominal belum ditemukan",
    )

    with pytest.raises(TransactionServiceError, match="Preview belum valid"):
        save_confirmed_transaction(connection, user_id=user_id, preview=error_preview)
