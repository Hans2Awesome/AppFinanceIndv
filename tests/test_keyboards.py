"""Tests for Telegram bot keyboards."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup

from bot04.bot.keyboards import (
    CALLBACK_ADD_EXPENSE,
    CALLBACK_ADD_INCOME,
    CALLBACK_ADD_INVESTMENT,
    CALLBACK_CATEGORIES,
    CALLBACK_REPORTS,
    CALLBACK_SETTINGS,
    build_main_menu_keyboard,
)


def test_build_main_menu_keyboard_returns_inline_keyboard_markup() -> None:
    keyboard = build_main_menu_keyboard()

    assert isinstance(keyboard, InlineKeyboardMarkup)


def test_build_main_menu_keyboard_has_expected_buttons_and_callbacks() -> None:
    keyboard = build_main_menu_keyboard()

    rows = keyboard.inline_keyboard
    assert [[button.text for button in row] for row in rows] == [
        ["➕ Pemasukan", "➖ Pengeluaran"],
        ["📈 Investasi", "📊 Laporan"],
        ["🗂 Kategori", "⚙️ Pengaturan"],
    ]
    assert [[button.callback_data for button in row] for row in rows] == [
        [CALLBACK_ADD_INCOME, CALLBACK_ADD_EXPENSE],
        [CALLBACK_ADD_INVESTMENT, CALLBACK_REPORTS],
        [CALLBACK_CATEGORIES, CALLBACK_SETTINGS],
    ]
