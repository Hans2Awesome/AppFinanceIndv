"""Tests for manual expense flow handler helpers."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from telegram import InlineKeyboardMarkup

from bot04.bot.handlers_manual_expense import (
    CALLBACK_MANUAL_EXPENSE_CANCEL,
    CALLBACK_MANUAL_EXPENSE_CATEGORY_PREFIX,
    CALLBACK_MANUAL_EXPENSE_START,
    ManualExpenseResponse,
    handle_manual_expense_amount_text,
    handle_manual_expense_callback,
)
from bot04.services.pending_store import PendingConfirmationStore
from finance_core.db.categories import seed_default_categories
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.db.transactions import list_transactions
from finance_core.db.users import get_or_create_user


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


def expense_category_id(connection: sqlite3.Connection, user_id: int, name: str = "Makan & Minum") -> int:
    return connection.execute(
        "SELECT id FROM categories WHERE user_id = ? AND type = 'expense' AND name = ?",
        (user_id, name),
    ).fetchone()[0]


def test_start_manual_expense_flow_shows_expense_category_buttons() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()

    response = handle_manual_expense_callback(
        CALLBACK_MANUAL_EXPENSE_START,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response is not None
    assert response.text == "Pilih kategori pengeluaran:"
    assert isinstance(response.reply_markup, InlineKeyboardMarkup)
    button_texts = [button.text for row in response.reply_markup.inline_keyboard for button in row]
    assert button_texts == [
        "Makan & Minum",
        "Transportasi",
        "Belanja",
        "Tagihan",
        "Hiburan",
        "Kesehatan",
        "Pendidikan",
        "Lainnya",
        "❌ Batal",
    ]
    assert store.get(telegram_user_id=796529359) is None


def test_select_expense_category_asks_for_amount_and_stores_pending_draft() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    category_id = expense_category_id(connection, user_id)

    response = handle_manual_expense_callback(
        f"{CALLBACK_MANUAL_EXPENSE_CATEGORY_PREFIX}{category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == ManualExpenseResponse(
        text="Masukkan nominal pengeluaran untuk kategori Makan & Minum.\nContoh: 25000 atau Rp25.000",
        reply_markup=None,
    )
    pending = store.get(telegram_user_id=796529359)
    assert pending is not None
    assert pending.type == "expense"
    assert pending.category_name == "Makan & Minum"
    assert pending.amount is None
    assert pending.error is None


def test_amount_text_builds_expense_preview_and_confirmation_keyboard() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    category_id = expense_category_id(connection, user_id)
    handle_manual_expense_callback(
        f"{CALLBACK_MANUAL_EXPENSE_CATEGORY_PREFIX}{category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    response = handle_manual_expense_amount_text(
        "Rp25.000 kopi pagi",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response is not None
    assert "Saya mendeteksi transaksi:" in response.text
    assert "Tipe: Pengeluaran" in response.text
    assert "Kategori: Makan & Minum" in response.text
    assert "Nominal: Rp25.000" in response.text
    assert isinstance(response.reply_markup, InlineKeyboardMarkup)
    pending = store.get(telegram_user_id=796529359)
    assert pending is not None
    assert pending.amount == 25_000
    assert pending.note == "kopi pagi"


def test_amount_text_without_pending_draft_is_ignored() -> None:
    store = make_store()

    response = handle_manual_expense_amount_text(
        "25000",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response is None


def test_amount_text_with_invalid_nominal_returns_help_and_keeps_draft() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    category_id = expense_category_id(connection, user_id)
    handle_manual_expense_callback(
        f"{CALLBACK_MANUAL_EXPENSE_CATEGORY_PREFIX}{category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    response = handle_manual_expense_amount_text(
        "kopi pagi",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response == ManualExpenseResponse(
        text="Nominal belum ditemukan. Masukkan nominal, contoh: 25000",
        reply_markup=None,
    )
    assert store.get(telegram_user_id=796529359).amount is None


def test_cancel_manual_expense_flow_clears_draft_without_saving() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    category_id = expense_category_id(connection, user_id)
    handle_manual_expense_callback(
        f"{CALLBACK_MANUAL_EXPENSE_CATEGORY_PREFIX}{category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    response = handle_manual_expense_callback(
        CALLBACK_MANUAL_EXPENSE_CANCEL,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == ManualExpenseResponse(text="❌ Input pengeluaran dibatalkan.", reply_markup=None)
    assert store.get(telegram_user_id=796529359) is None
    assert list_transactions(
        connection,
        user_id=user_id,
        start_date="2026-05-30",
        end_date="2026-05-30",
    ) == []
