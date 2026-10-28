"""Tests for manual investment flow handler helpers."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from telegram import InlineKeyboardMarkup

from bot04.bot.handlers_manual_investment import (
    CALLBACK_MANUAL_INVESTMENT_CANCEL,
    CALLBACK_MANUAL_INVESTMENT_CATEGORY_PREFIX,
    CALLBACK_MANUAL_INVESTMENT_START,
    ManualInvestmentResponse,
    handle_manual_investment_amount_text,
    handle_manual_investment_callback,
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


def investment_category_id(connection: sqlite3.Connection, user_id: int, name: str = "Crypto") -> int:
    return connection.execute(
        "SELECT id FROM categories WHERE user_id = ? AND type = 'investment' AND name = ?",
        (user_id, name),
    ).fetchone()[0]


def test_start_manual_investment_flow_shows_investment_category_buttons() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()

    response = handle_manual_investment_callback(
        CALLBACK_MANUAL_INVESTMENT_START,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response is not None
    assert response.text == "Pilih jenis investasi:"
    assert isinstance(response.reply_markup, InlineKeyboardMarkup)
    button_texts = [button.text for row in response.reply_markup.inline_keyboard for button in row]
    assert button_texts == ["Saham", "Crypto", "Reksadana", "Emas", "Deposito", "Lainnya", "❌ Batal"]
    assert store.get(telegram_user_id=796529359) is None


def test_select_investment_category_asks_for_amount_and_stores_pending_draft() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    category_id = investment_category_id(connection, user_id)

    response = handle_manual_investment_callback(
        f"{CALLBACK_MANUAL_INVESTMENT_CATEGORY_PREFIX}{category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == ManualInvestmentResponse(
        text="Masukkan nominal investasi untuk kategori Crypto.\nContoh: 100000 atau Rp100.000",
        reply_markup=None,
    )
    pending = store.get(telegram_user_id=796529359)
    assert pending is not None
    assert pending.type == "investment"
    assert pending.category_name == "Crypto"
    assert pending.amount is None
    assert pending.asset_name == "Crypto"
    assert pending.error is None


def test_amount_text_builds_investment_preview_and_confirmation_keyboard() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    category_id = investment_category_id(connection, user_id)
    handle_manual_investment_callback(
        f"{CALLBACK_MANUAL_INVESTMENT_CATEGORY_PREFIX}{category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    response = handle_manual_investment_amount_text(
        "Rp100.000 btc dca mingguan",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response is not None
    assert "Saya mendeteksi transaksi:" in response.text
    assert "Tipe: Investasi" in response.text
    assert "Kategori: Crypto" in response.text
    assert "Nominal: Rp100.000" in response.text
    assert "Aset: BTC" in response.text
    assert isinstance(response.reply_markup, InlineKeyboardMarkup)
    pending = store.get(telegram_user_id=796529359)
    assert pending is not None
    assert pending.amount == 100_000
    assert pending.asset_name == "BTC"
    assert pending.note == "dca mingguan"


def test_amount_text_without_pending_draft_is_ignored() -> None:
    store = make_store()

    response = handle_manual_investment_amount_text(
        "100000 btc",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response is None


def test_amount_text_with_invalid_nominal_returns_help_and_keeps_draft() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    category_id = investment_category_id(connection, user_id)
    handle_manual_investment_callback(
        f"{CALLBACK_MANUAL_INVESTMENT_CATEGORY_PREFIX}{category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    response = handle_manual_investment_amount_text(
        "btc dca mingguan",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response == ManualInvestmentResponse(
        text="Nominal belum ditemukan. Masukkan nominal, contoh: 100000",
        reply_markup=None,
    )
    assert store.get(telegram_user_id=796529359).amount is None


def test_cancel_manual_investment_flow_clears_draft_without_saving() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    store = make_store()
    category_id = investment_category_id(connection, user_id)
    handle_manual_investment_callback(
        f"{CALLBACK_MANUAL_INVESTMENT_CATEGORY_PREFIX}{category_id}",
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    response = handle_manual_investment_callback(
        CALLBACK_MANUAL_INVESTMENT_CANCEL,
        connection=connection,
        user_id=user_id,
        telegram_user_id=796529359,
        pending_store=store,
    )

    assert response == ManualInvestmentResponse(text="❌ Input investasi dibatalkan.", reply_markup=None)
    assert store.get(telegram_user_id=796529359) is None
    assert list_transactions(
        connection,
        user_id=user_id,
        start_date="2026-05-30",
        end_date="2026-05-30",
    ) == []
