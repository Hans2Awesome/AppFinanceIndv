"""Telegram inline keyboards for Bot04."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CALLBACK_ADD_INCOME = "add_income"
CALLBACK_ADD_EXPENSE = "add_expense"
CALLBACK_ADD_INVESTMENT = "add_investment"
CALLBACK_REPORTS = "reports"
CALLBACK_CATEGORIES = "categories"
CALLBACK_SETTINGS = "settings"


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the Bot04 main menu inline keyboard."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Pemasukan", callback_data=CALLBACK_ADD_INCOME),
                InlineKeyboardButton("➖ Pengeluaran", callback_data=CALLBACK_ADD_EXPENSE),
            ],
            [
                InlineKeyboardButton("📈 Investasi", callback_data=CALLBACK_ADD_INVESTMENT),
                InlineKeyboardButton("📊 Laporan", callback_data=CALLBACK_REPORTS),
            ],
            [
                InlineKeyboardButton("🗂 Kategori", callback_data=CALLBACK_CATEGORIES),
                InlineKeyboardButton("⚙️ Pengaturan", callback_data=CALLBACK_SETTINGS),
            ],
        ]
    )
