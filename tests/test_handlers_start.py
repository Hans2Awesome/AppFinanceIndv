"""Tests for /start and /menu handler logic."""

from __future__ import annotations

import sqlite3

from telegram import InlineKeyboardMarkup

from bot04.bot.handlers_start import build_start_response, register_start_user
from bot04.bot.keyboards import build_main_menu_keyboard
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def test_register_start_user_gets_or_creates_user_and_seeds_default_categories() -> None:
    connection = setup_connection()

    user = register_start_user(
        connection,
        telegram_user_id=796529359,
        first_name="Hans",
        username="hans2awesome",
    )

    assert user.telegram_user_id == 796529359
    assert user.first_name == "Hans"
    assert user.username == "hans2awesome"
    category_count = connection.execute(
        "SELECT COUNT(*) FROM categories WHERE user_id = ?",
        (user.id,),
    ).fetchone()[0]
    assert category_count == 20


def test_register_start_user_is_idempotent() -> None:
    connection = setup_connection()

    first_user = register_start_user(
        connection,
        telegram_user_id=796529359,
        first_name="Hans",
        username="hans2awesome",
    )
    second_user = register_start_user(
        connection,
        telegram_user_id=796529359,
        first_name="Changed",
        username="changed",
    )

    assert second_user == first_user
    user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    category_count = connection.execute(
        "SELECT COUNT(*) FROM categories WHERE user_id = ?",
        (first_user.id,),
    ).fetchone()[0]
    assert user_count == 1
    assert category_count == 20


def test_build_start_response_returns_welcome_message_and_main_menu_keyboard() -> None:
    message, keyboard = build_start_response(first_name="Hans")

    assert "Halo Hans" in message
    assert "Bot04" in message
    assert "catat pemasukan, pengeluaran, dan investasi" in message
    assert keyboard == build_main_menu_keyboard()
    assert isinstance(keyboard, InlineKeyboardMarkup)


def test_build_start_response_handles_missing_first_name() -> None:
    message, _keyboard = build_start_response(first_name=None)

    assert "Halo" in message
    assert "None" not in message
