"""Tests for quick input confirmation callback handler helpers."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from bot04.bot.handlers_confirm import (
    ConfirmHandlerResponse,
    handle_quick_confirm_callback,
)
from bot04.bot.handlers_quick_input import CALLBACK_QUICK_CANCEL, CALLBACK_QUICK_SAVE
from bot04.services.pending_store import PendingConfirmationStore
from finance_core.db.categories import seed_default_categories
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.db.transactions import list_transactions
from finance_core.db.users import get_or_create_user
from finance_core.services.quick_input_parser import QuickInputResult


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def setup_user(connection: sqlite3.Connection, telegram_user_id: int = 796529359) -> int:
    user = get_or_create_user(connection, telegram_user_id=telegram_user_id)
    seed_default_categories(connection, user.id)
    return user.id


def make_store() -> PendingConfirmationStore:
    return PendingConfirmationStore(
        now_provider=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)
    )


def preview() -> QuickInputResult:
    return QuickInputResult(
        type="expense",
        category_name="Makan & Minum",
        amount=25000,
        note="kopi pagi",
        asset_name=None,
        transaction_date=date(2026, 5, 30),
        confidence=1.0,
        needs_review=False,
        original_text="makan 25000 kopi pagi",
        error=None,
    )


def test_quick_save_saves_pending_transaction_and_clears_pending_preview() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    store.set(telegram_user_id=796529359, preview=preview())

    response = handle_quick_confirm_callback(
        CALLBACK_QUICK_SAVE,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == ConfirmHandlerResponse(
        text="✅ Transaksi berhasil disimpan.\n\nPengeluaran Makan & Minum Rp25.000 sudah tercatat.",
        reply_markup=None,
    )
    assert store.get(telegram_user_id=796529359) is None
    transactions = list_transactions(
        connection,
        user_id=user_id,
        start_date="2026-05-30",
        end_date="2026-05-30",
    )
    assert len(transactions) == 1
    assert transactions[0].amount == 25000
    assert transactions[0].note == "kopi pagi"


def test_quick_cancel_clears_pending_preview_without_saving_transaction() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    store.set(telegram_user_id=796529359, preview=preview())

    response = handle_quick_confirm_callback(
        CALLBACK_QUICK_CANCEL,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == ConfirmHandlerResponse(
        text="❌ Transaksi dibatalkan.",
        reply_markup=None,
    )
    assert store.get(telegram_user_id=796529359) is None
    assert connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0


def test_quick_save_without_pending_preview_returns_expired_message() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()

    response = handle_quick_confirm_callback(
        CALLBACK_QUICK_SAVE,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == ConfirmHandlerResponse(
        text="Preview transaksi sudah expired atau tidak ditemukan. Silakan ketik transaksi lagi.",
        reply_markup=None,
    )
    assert connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0


def test_quick_cancel_without_pending_preview_returns_expired_message() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()

    response = handle_quick_confirm_callback(
        CALLBACK_QUICK_CANCEL,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == ConfirmHandlerResponse(
        text="Preview transaksi sudah expired atau tidak ditemukan. Silakan ketik transaksi lagi.",
        reply_markup=None,
    )


def test_unknown_callback_is_ignored() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()

    response = handle_quick_confirm_callback(
        "unknown",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response is None
