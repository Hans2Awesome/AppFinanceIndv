"""Tests for manual income flow handler helpers."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from telegram import InlineKeyboardMarkup

from bot04.bot.handlers_manual_income import (
    CALLBACK_MANUAL_INCOME_CANCEL,
    CALLBACK_MANUAL_INCOME_CATEGORY_PREFIX,
    CALLBACK_MANUAL_INCOME_START,
    ManualIncomeResponse,
    handle_manual_income_amount_text,
    handle_manual_income_callback,
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


def test_start_manual_income_flow_shows_income_category_buttons() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()

    response = handle_manual_income_callback(
        CALLBACK_MANUAL_INCOME_START,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response is not None
    assert response.text == "Pilih kategori pemasukan:"
    assert isinstance(response.reply_markup, InlineKeyboardMarkup)
    button_texts = [
        button.text
        for row in response.reply_markup.inline_keyboard
        for button in row
    ]
    assert button_texts == ["Gaji", "Bonus", "Freelance", "Bisnis", "Hadiah", "Lainnya", "❌ Batal"]
    assert store.get(telegram_user_id=796529359) is None


def test_select_income_category_asks_for_amount_and_stores_pending_draft() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    gaji_category_id = connection.execute(
        "SELECT id FROM categories WHERE user_id = ? AND type = 'income' AND name = 'Gaji'",
        (user_id,),
    ).fetchone()[0]

    response = handle_manual_income_callback(
        f"{CALLBACK_MANUAL_INCOME_CATEGORY_PREFIX}{gaji_category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == ManualIncomeResponse(
        text="Masukkan nominal pemasukan untuk kategori Gaji.\nContoh: 5000000 atau Rp5.000.000",
        reply_markup=None,
    )
    pending = store.get(telegram_user_id=796529359)
    assert pending is not None
    assert pending.type == "income"
    assert pending.category_name == "Gaji"
    assert pending.amount is None
    assert pending.error is None


def test_amount_text_builds_preview_and_confirmation_keyboard() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    gaji_category_id = connection.execute(
        "SELECT id FROM categories WHERE user_id = ? AND type = 'income' AND name = 'Gaji'",
        (user_id,),
    ).fetchone()[0]
    handle_manual_income_callback(
        f"{CALLBACK_MANUAL_INCOME_CATEGORY_PREFIX}{gaji_category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    response = handle_manual_income_amount_text(
        "Rp5.000.000 gaji mei",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response is not None
    assert "Saya mendeteksi transaksi:" in response.text
    assert "Tipe: Pemasukan" in response.text
    assert "Kategori: Gaji" in response.text
    assert "Nominal: Rp5.000.000" in response.text
    assert isinstance(response.reply_markup, InlineKeyboardMarkup)
    pending = store.get(telegram_user_id=796529359)
    assert pending is not None
    assert pending.amount == 5_000_000
    assert pending.note == "gaji mei"


def test_amount_text_without_pending_draft_is_ignored() -> None:
    store = make_store()

    response = handle_manual_income_amount_text(
        "5000000",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response is None


def test_amount_text_with_invalid_nominal_returns_help_and_keeps_draft() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    gaji_category_id = connection.execute(
        "SELECT id FROM categories WHERE user_id = ? AND type = 'income' AND name = 'Gaji'",
        (user_id,),
    ).fetchone()[0]
    handle_manual_income_callback(
        f"{CALLBACK_MANUAL_INCOME_CATEGORY_PREFIX}{gaji_category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    response = handle_manual_income_amount_text(
        "gaji mei",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response == ManualIncomeResponse(
        text="Nominal belum ditemukan. Masukkan nominal, contoh: 5000000",
        reply_markup=None,
    )
    assert store.get(telegram_user_id=796529359).amount is None


def test_cancel_manual_income_flow_clears_draft_without_saving() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    gaji_category_id = connection.execute(
        "SELECT id FROM categories WHERE user_id = ? AND type = 'income' AND name = 'Gaji'",
        (user_id,),
    ).fetchone()[0]
    handle_manual_income_callback(
        f"{CALLBACK_MANUAL_INCOME_CATEGORY_PREFIX}{gaji_category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    response = handle_manual_income_callback(
        CALLBACK_MANUAL_INCOME_CANCEL,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == ManualIncomeResponse(text="❌ Input pemasukan dibatalkan.", reply_markup=None)
    assert store.get(telegram_user_id=796529359) is None
    assert list_transactions(
        connection,
        user_id=user_id,
        start_date="2026-05-30",
        end_date="2026-05-30",
    ) == []
