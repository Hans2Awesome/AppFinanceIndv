"""Tests for Bot04 Telegram application wiring."""

from __future__ import annotations

import sqlite3

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
)

from bot04.bot.app import (
    BOT_COMMANDS,
    BotDependencies,
    build_application,
    build_handlers,
)
from bot04.bot.handlers_manual_expense import CALLBACK_MANUAL_EXPENSE_START
from bot04.bot.handlers_manual_income import CALLBACK_MANUAL_INCOME_START
from bot04.bot.handlers_manual_investment import CALLBACK_MANUAL_INVESTMENT_START
from bot04.bot.handlers_quick_input import CALLBACK_QUICK_CANCEL, CALLBACK_QUICK_SAVE
from bot04.bot.handlers_reports import (
    CALLBACK_REPORT_BACK_TO_MENU,
    CALLBACK_REPORT_EXPENSE_LOG_PREFIX,
    CALLBACK_REPORT_INCOME_LOG_PREFIX,
)
from bot04.bot.handlers_transactions import CALLBACK_TRANSACTIONS_RECENT
from bot04.config import Config
from bot04.services.pending_store import PendingConfirmationStore
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def make_dependencies() -> BotDependencies:
    return BotDependencies(connection=setup_connection(), pending_store=PendingConfirmationStore())


def test_build_handlers_registers_commands_callbacks_and_quick_input_message_handler() -> None:
    handlers = build_handlers(make_dependencies())

    command_handlers = [handler for handler in handlers if isinstance(handler, CommandHandler)]
    callback_handlers = [handler for handler in handlers if isinstance(handler, CallbackQueryHandler)]
    message_handlers = [handler for handler in handlers if isinstance(handler, MessageHandler)]

    command_sets = [handler.commands for handler in command_handlers]
    assert {"start"} in command_sets
    assert {"menu"} in command_sets
    assert {"today"} in command_sets
    assert {"week"} in command_sets
    assert {"month"} in command_sets
    assert {"report"} in command_sets
    assert {"riwayat_pemasukan"} in command_sets
    assert {"riwayat_pengeluaran"} in command_sets
    assert {"help"} in command_sets
    assert len(callback_handlers) >= 2
    assert any(CALLBACK_QUICK_SAVE in str(handler.pattern) for handler in callback_handlers)
    assert any(CALLBACK_QUICK_CANCEL in str(handler.pattern) for handler in callback_handlers)
    assert any(CALLBACK_MANUAL_INCOME_START in str(handler.pattern) for handler in callback_handlers)
    assert any(CALLBACK_MANUAL_EXPENSE_START in str(handler.pattern) for handler in callback_handlers)
    assert any(CALLBACK_MANUAL_INVESTMENT_START in str(handler.pattern) for handler in callback_handlers)
    assert any(CALLBACK_TRANSACTIONS_RECENT in str(handler.pattern) for handler in callback_handlers)
    assert any(f"{CALLBACK_REPORT_INCOME_LOG_PREFIX}\\\\d+" in str(handler.pattern) for handler in callback_handlers)
    assert any(f"{CALLBACK_REPORT_EXPENSE_LOG_PREFIX}\\\\d+" in str(handler.pattern) for handler in callback_handlers)
    assert any(CALLBACK_REPORT_BACK_TO_MENU in str(handler.pattern) for handler in callback_handlers)
    assert len(message_handlers) == 1


def test_build_application_stores_dependencies_and_registers_handlers() -> None:
    dependencies = make_dependencies()
    config = Config(
        bot_token="123456:ABCDEF_fake_token_for_tests",
        database_path=":memory:",
        timezone="Asia/Jakarta",
        currency="IDR",
    )

    application = build_application(config=config, dependencies=dependencies)

    assert isinstance(application, Application)
    assert application.bot_data["connection"] is dependencies.connection
    assert application.bot_data["pending_store"] is dependencies.pending_store
    assert application.post_init is not None
    registered_handlers = [handler for group in application.handlers.values() for handler in group]
    assert any(isinstance(handler, CommandHandler) for handler in registered_handlers)
    assert any(isinstance(handler, CallbackQueryHandler) for handler in registered_handlers)
    assert any(isinstance(handler, MessageHandler) for handler in registered_handlers)


def test_bot_commands_match_bot03_style_menu_for_bot04() -> None:
    assert [(command.command, command.description) for command in BOT_COMMANDS] == [
        ("start", "🚀 Jalankan Bot"),
        ("menu", "📋 Menu Utama"),
        ("help", "💡 Bantuan Input Cepat"),
        ("today", "📅 Laporan Hari Ini"),
        ("week", "🗓 Laporan Minggu Ini"),
        ("month", "📆 Laporan Bulan Ini"),
        ("report", "📊 Menu Laporan"),
        ("riwayat_pemasukan", "💰 Riwayat Pemasukan"),
        ("riwayat_pengeluaran", "💸 Riwayat Pengeluaran"),
    ]


def test_build_application_creates_sqlite_connection_when_dependencies_not_supplied() -> None:
    config = Config(
        bot_token="123456:ABCDEF_fake_token_for_tests",
        database_path=":memory:",
        timezone="Asia/Jakarta",
        currency="IDR",
    )

    application = build_application(config=config)

    assert "connection" in application.bot_data
    assert "pending_store" in application.bot_data
    application.bot_data["connection"].execute("SELECT COUNT(*) FROM users")
