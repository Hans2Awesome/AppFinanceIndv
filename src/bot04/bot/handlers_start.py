"""Start/menu handler helpers for Bot04 Telegram bot."""

from __future__ import annotations

import sqlite3

from telegram import InlineKeyboardMarkup

from bot04.bot.keyboards import build_main_menu_keyboard
from finance_core.db.categories import seed_default_categories
from finance_core.db.users import User, get_or_create_user

WELCOME_MESSAGE_TEMPLATE = """Halo {name} 👋

Selamat datang di Bot04.
Bot ini membantu kamu catat pemasukan, pengeluaran, dan investasi secara cepat.

Kamu juga bisa langsung mengetik transaksi, misalnya:
- makan 25000
- gaji 5000000
- btc 100000 dca mingguan

Pilih menu di bawah untuk mulai."""


def register_start_user(
    connection: sqlite3.Connection,
    *,
    telegram_user_id: int,
    first_name: str | None = None,
    username: str | None = None,
) -> User:
    """Get-or-create a Telegram user and seed their default categories."""

    user = get_or_create_user(
        connection,
        telegram_user_id=telegram_user_id,
        first_name=first_name,
        username=username,
    )
    seed_default_categories(connection, user.id)
    return user


def build_start_response(first_name: str | None) -> tuple[str, InlineKeyboardMarkup]:
    """Build the welcome message and main menu keyboard for /start or /menu."""

    display_name = first_name.strip() if first_name and first_name.strip() else ""
    greeting_name = display_name or ""
    return (
        WELCOME_MESSAGE_TEMPLATE.format(name=greeting_name).replace("Halo  👋", "Halo 👋"),
        build_main_menu_keyboard(),
    )
