"""Tests for quick input message handler helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone

from telegram import InlineKeyboardMarkup

from bot04.bot.handlers_quick_input import (
    CALLBACK_QUICK_CANCEL,
    CALLBACK_QUICK_EDIT,
    CALLBACK_QUICK_SAVE,
    QuickInputHandlerResponse,
    handle_quick_input_text,
)
from bot04.services.pending_store import PendingConfirmationStore


def make_store() -> PendingConfirmationStore:
    return PendingConfirmationStore(
        now_provider=lambda: datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)
    )


def test_handle_quick_input_ignores_commands() -> None:
    store = make_store()

    response = handle_quick_input_text(
        "/start",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response is None
    assert store.get(telegram_user_id=796529359) is None


def test_handle_quick_input_returns_help_message_when_parser_errors() -> None:
    store = make_store()

    response = handle_quick_input_text(
        "makan siang",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    assert response == QuickInputHandlerResponse(
        text=(
            "Nominal belum ditemukan\n\n"
            "Contoh input cepat:\n"
            "- makan 25000\n"
            "- gaji 5000000\n"
            "- btc 100000 dca mingguan"
        ),
        reply_markup=None,
    )
    assert store.get(telegram_user_id=796529359) is None


def test_handle_quick_input_stores_pending_preview_and_returns_confirmation_keyboard() -> None:
    store = make_store()

    response = handle_quick_input_text(
        "makan 25000",
        telegram_user_id=796529359,
        pending_store=store,
        today=date(2026, 5, 30),
    )

    pending = store.get(telegram_user_id=796529359)
    assert pending is not None
    assert pending.amount == 25000
    assert pending.type == "expense"
    assert response is not None
    assert "Saya mendeteksi transaksi:" in response.text
    assert "Nominal: Rp25.000" in response.text
    assert isinstance(response.reply_markup, InlineKeyboardMarkup)
    assert [[button.text for button in row] for row in response.reply_markup.inline_keyboard] == [
        ["✅ Simpan", "✏️ Edit", "❌ Batal"]
    ]
    assert [[button.callback_data for button in row] for row in response.reply_markup.inline_keyboard] == [
        [CALLBACK_QUICK_SAVE, CALLBACK_QUICK_EDIT, CALLBACK_QUICK_CANCEL]
    ]
