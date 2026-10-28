"""Tests for transaction list/edit/delete handler helpers."""

from __future__ import annotations

import sqlite3

from telegram import InlineKeyboardMarkup

from bot04.bot.handlers_transactions import (
    CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX,
    CALLBACK_TRANSACTION_DELETE_PREFIX,
    CALLBACK_TRANSACTION_EDIT_PREFIX,
    CALLBACK_TRANSACTIONS_RECENT,
    TransactionHandlerResponse,
    handle_transaction_edit_text,
    handle_transactions_callback,
)
from bot04.services.pending_store import PendingConfirmationStore
from finance_core.db.categories import seed_default_categories
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.db.transactions import create_transaction, list_transactions
from finance_core.db.users import get_or_create_user


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def setup_user(connection: sqlite3.Connection, telegram_user_id: int = 796529359) -> int:
    user = get_or_create_user(connection, telegram_user_id=telegram_user_id)
    seed_default_categories(connection, user.id)
    return user.id


def category_id(connection: sqlite3.Connection, user_id: int, type: str, name: str) -> int:
    row = connection.execute(
        "SELECT id FROM categories WHERE user_id = ? AND type = ? AND name = ?",
        (user_id, type, name),
    ).fetchone()
    assert row is not None
    return row[0]


def add_expense(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    amount: int,
    note: str,
    transaction_date: str,
) -> int:
    transaction = create_transaction(
        connection,
        user_id=user_id,
        type="expense",
        category_id=category_id(connection, user_id, "expense", "Makan & Minum"),
        amount=amount,
        note=note,
        asset_name=None,
        transaction_date=transaction_date,
    )
    return transaction.id


def test_recent_transactions_lists_latest_user_transactions_with_action_buttons() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    other_user_id = setup_user(connection, telegram_user_id=123)
    first_id = add_expense(
        connection,
        user_id=user_id,
        amount=25_000,
        note="kopi",
        transaction_date="2026-05-29",
    )
    second_id = add_expense(
        connection,
        user_id=user_id,
        amount=50_000,
        note="makan siang",
        transaction_date="2026-05-30",
    )
    add_expense(
        connection,
        user_id=other_user_id,
        amount=99_000,
        note="other user",
        transaction_date="2026-05-30",
    )

    response = handle_transactions_callback(
        CALLBACK_TRANSACTIONS_RECENT,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=PendingConfirmationStore(),
    )

    assert response is not None
    assert response.text.startswith("Transaksi terakhir:")
    assert "Rp50.000" in response.text
    assert "makan siang" in response.text
    assert "Rp25.000" in response.text
    assert "other user" not in response.text
    assert isinstance(response.reply_markup, InlineKeyboardMarkup)
    button_data = [button.callback_data for row in response.reply_markup.inline_keyboard for button in row]
    assert f"{CALLBACK_TRANSACTION_EDIT_PREFIX}{second_id}" in button_data
    assert f"{CALLBACK_TRANSACTION_DELETE_PREFIX}{second_id}" in button_data
    assert f"{CALLBACK_TRANSACTION_EDIT_PREFIX}{first_id}" in button_data
    assert f"{CALLBACK_TRANSACTION_DELETE_PREFIX}{first_id}" in button_data


def test_delete_callback_requires_confirmation_before_deleting() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    transaction_id = add_expense(
        connection,
        user_id=user_id,
        amount=25_000,
        note="kopi",
        transaction_date="2026-05-30",
    )

    response = handle_transactions_callback(
        f"{CALLBACK_TRANSACTION_DELETE_PREFIX}{transaction_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=PendingConfirmationStore(),
    )

    assert response is not None
    assert response.text == "Yakin hapus transaksi Rp25.000 — kopi?"
    assert [[button.text for button in row] for row in response.reply_markup.inline_keyboard] == [
        ["✅ Ya, hapus", "❌ Batal"]
    ]
    assert len(list_transactions(connection, user_id=user_id, start_date="2026-05-01", end_date="2026-05-31")) == 1


def test_delete_confirm_removes_owned_transaction() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    other_user_id = setup_user(connection, telegram_user_id=123)
    transaction_id = add_expense(
        connection,
        user_id=user_id,
        amount=25_000,
        note="kopi",
        transaction_date="2026-05-30",
    )
    other_transaction_id = add_expense(
        connection,
        user_id=other_user_id,
        amount=99_000,
        note="other user",
        transaction_date="2026-05-30",
    )

    response = handle_transactions_callback(
        f"{CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX}{transaction_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=PendingConfirmationStore(),
    )
    blocked = handle_transactions_callback(
        f"{CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX}{other_transaction_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=PendingConfirmationStore(),
    )

    assert response == TransactionHandlerResponse(text="✅ Transaksi berhasil dihapus.", reply_markup=None)
    assert blocked == TransactionHandlerResponse(text="Transaksi tidak ditemukan.", reply_markup=None)
    assert list_transactions(connection, user_id=user_id, start_date="2026-05-01", end_date="2026-05-31") == []
    assert len(list_transactions(connection, user_id=other_user_id, start_date="2026-05-01", end_date="2026-05-31")) == 1


def test_edit_callback_prompts_for_new_amount_and_note() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    transaction_id = add_expense(
        connection,
        user_id=user_id,
        amount=25_000,
        note="kopi",
        transaction_date="2026-05-30",
    )
    store = PendingConfirmationStore()

    response = handle_transactions_callback(
        f"{CALLBACK_TRANSACTION_EDIT_PREFIX}{transaction_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == TransactionHandlerResponse(
        text="Kirim nominal/catatan baru untuk transaksi ini.\nContoh: 30000 kopi sore",
        reply_markup=None,
    )
    pending = store.get(telegram_user_id=796529359)
    assert pending is not None
    assert pending.original_text == f"edit_transaction:{transaction_id}"


def test_edit_text_updates_amount_and_note_for_pending_transaction() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    transaction_id = add_expense(
        connection,
        user_id=user_id,
        amount=25_000,
        note="kopi",
        transaction_date="2026-05-30",
    )
    store = PendingConfirmationStore()
    handle_transactions_callback(
        f"{CALLBACK_TRANSACTION_EDIT_PREFIX}{transaction_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    response = handle_transaction_edit_text(
        "30.000 kopi sore",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == TransactionHandlerResponse(
        text="✅ Transaksi berhasil diupdate menjadi Rp30.000 — kopi sore.",
        reply_markup=None,
    )
    transactions = list_transactions(connection, user_id=user_id, start_date="2026-05-01", end_date="2026-05-31")
    assert transactions[0].amount == 30_000
    assert transactions[0].note == "kopi sore"
    assert store.get(telegram_user_id=796529359) is None


def test_edit_text_without_pending_edit_is_ignored() -> None:
    response = handle_transaction_edit_text(
        "30.000 kopi sore",
        connection=setup_connection(),
        user_id=1,
        telegram_user_id=796529359,
        pending_store=PendingConfirmationStore(),
    )

    assert response is None
