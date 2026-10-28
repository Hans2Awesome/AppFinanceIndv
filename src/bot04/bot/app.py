"""Telegram application wiring for Bot04."""

from __future__ import annotations

import asyncio
import functools
import sqlite3
import threading
from dataclasses import dataclass
from typing import Callable

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot04.bot.handlers_confirm import handle_quick_confirm_callback
from bot04.bot.handlers_manual_expense import (
    CALLBACK_MANUAL_EXPENSE_CANCEL,
    CALLBACK_MANUAL_EXPENSE_CATEGORY_PREFIX,
    CALLBACK_MANUAL_EXPENSE_START,
    handle_manual_expense_amount_text,
    handle_manual_expense_callback,
)
from bot04.bot.handlers_manual_income import (
    CALLBACK_MANUAL_INCOME_CANCEL,
    CALLBACK_MANUAL_INCOME_CATEGORY_PREFIX,
    CALLBACK_MANUAL_INCOME_START,
    handle_manual_income_amount_text,
    handle_manual_income_callback,
)
from bot04.bot.handlers_manual_investment import (
    CALLBACK_MANUAL_INVESTMENT_CANCEL,
    CALLBACK_MANUAL_INVESTMENT_CATEGORY_PREFIX,
    CALLBACK_MANUAL_INVESTMENT_START,
    handle_manual_investment_amount_text,
    handle_manual_investment_callback,
)
from bot04.bot.handlers_quick_input import (
    CALLBACK_QUICK_CANCEL,
    CALLBACK_QUICK_SAVE,
    handle_quick_input_text,
)
from bot04.bot.handlers_reports import (
    CALLBACK_REPORT_BACK_TO_MENU,
    CALLBACK_REPORT_EXPENSE_CATEGORIES,
    CALLBACK_REPORT_EXPENSE_LOG_PREFIX,
    CALLBACK_REPORT_INCOME_CATEGORIES,
    CALLBACK_REPORT_INCOME_LOG_PREFIX,
    CALLBACK_REPORT_INVESTMENT,
    CALLBACK_REPORT_MONTH,
    CALLBACK_REPORT_TODAY,
    CALLBACK_REPORT_WEEK,
    build_category_report_response,
    build_investment_report_response,
    build_period_report_response,
    build_report_menu_response,
    build_transaction_log_response,
    parse_report_page,
)
from bot04.bot.handlers_start import build_start_response, register_start_user
from bot04.bot.handlers_transactions import (
    CALLBACK_TRANSACTION_DELETE_CANCEL,
    CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX,
    CALLBACK_TRANSACTION_DELETE_PREFIX,
    CALLBACK_TRANSACTION_EDIT_PREFIX,
    CALLBACK_TRANSACTIONS_RECENT,
    handle_transaction_edit_text,
    handle_transactions_callback,
)
from bot04.bot.help_text import build_help_text
from bot04.config import Config
from bot04.services.pending_store import PendingConfirmationStore
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.timezones import today_in

BOT_COMMANDS = [
    BotCommand("start", "🚀 Jalankan Bot"),
    BotCommand("menu", "📋 Menu Utama"),
    BotCommand("help", "💡 Bantuan Input Cepat"),
    BotCommand("today", "📅 Laporan Hari Ini"),
    BotCommand("week", "🗓 Laporan Minggu Ini"),
    BotCommand("month", "📆 Laporan Bulan Ini"),
    BotCommand("report", "📊 Menu Laporan"),
    BotCommand("riwayat_pemasukan", "💰 Riwayat Pemasukan"),
    BotCommand("riwayat_pengeluaran", "💸 Riwayat Pengeluaran"),
]


@dataclass(frozen=True)
class BotDependencies:
    """Runtime dependencies shared by Telegram handlers."""

    connection: sqlite3.Connection
    pending_store: PendingConfirmationStore


def build_application(
    *,
    config: Config,
    dependencies: BotDependencies | None = None,
) -> Application:
    """Build a python-telegram-bot Application and register all Bot04 handlers."""

    dependencies = dependencies or build_dependencies(config.database_path)
    application = ApplicationBuilder().token(config.bot_token).concurrent_updates(False).build()
    application.bot_data["connection"] = dependencies.connection
    application.bot_data["pending_store"] = dependencies.pending_store

    for handler in _committing_handlers(build_handlers(dependencies)):
        application.add_handler(handler)

    application.post_init = _set_bot_commands
    return application


async def _set_bot_commands(application: Application) -> None:
    """Publish Bot04 commands to Telegram's command menu."""

    await application.bot.set_my_commands(BOT_COMMANDS)


def build_dependencies(database_path: str) -> BotDependencies:
    """Create SQLite and pending-store dependencies for the bot runtime."""

    # The bot shares one connection across handler calls, so it must be usable
    # from the worker thread pool.
    connection = connect(database_path, check_same_thread=False)
    init_db(connection)
    return BotDependencies(
        connection=connection,
        pending_store=PendingConfirmationStore(),
    )


def build_handlers(dependencies: BotDependencies) -> list[BaseHandler]:
    """Build command, callback, and message handlers for the Telegram app."""

    # ``dependencies`` is accepted so tests can verify wiring without relying on
    # global state; PTB callbacks read the same objects from application.bot_data.
    _ = dependencies
    return [
        CommandHandler("start", _start_or_menu_command),
        CommandHandler("menu", _start_or_menu_command),
        CommandHandler("today", _today_command),
        CommandHandler("week", _week_command),
        CommandHandler("month", _month_command),
        CommandHandler("report", _report_command),
        CommandHandler("riwayat_pemasukan", _riwayat_pemasukan_command),
        CommandHandler("riwayat_pengeluaran", _riwayat_pengeluaran_command),
        CommandHandler("help", _help_command),
        CallbackQueryHandler(
            _quick_confirm_callback,
            pattern=f"^({CALLBACK_QUICK_SAVE}|{CALLBACK_QUICK_CANCEL})$",
        ),
        CallbackQueryHandler(
            _manual_income_callback,
            pattern=(
                f"^({CALLBACK_MANUAL_INCOME_START}|{CALLBACK_MANUAL_INCOME_CANCEL}|"
                f"{CALLBACK_MANUAL_INCOME_CATEGORY_PREFIX}\\d+)$"
            ),
        ),
        CallbackQueryHandler(
            _manual_expense_callback,
            pattern=(
                f"^({CALLBACK_MANUAL_EXPENSE_START}|{CALLBACK_MANUAL_EXPENSE_CANCEL}|"
                f"{CALLBACK_MANUAL_EXPENSE_CATEGORY_PREFIX}\\d+)$"
            ),
        ),
        CallbackQueryHandler(
            _manual_investment_callback,
            pattern=(
                f"^({CALLBACK_MANUAL_INVESTMENT_START}|{CALLBACK_MANUAL_INVESTMENT_CANCEL}|"
                f"{CALLBACK_MANUAL_INVESTMENT_CATEGORY_PREFIX}\\d+)$"
            ),
        ),
        CallbackQueryHandler(
            _transactions_callback,
            pattern=(
                f"^({CALLBACK_TRANSACTIONS_RECENT}|{CALLBACK_TRANSACTION_DELETE_CANCEL}|"
                f"{CALLBACK_TRANSACTION_EDIT_PREFIX}\\d+|{CALLBACK_TRANSACTION_DELETE_PREFIX}\\d+|"
                f"{CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX}\\d+)$"
            ),
        ),
        CallbackQueryHandler(
            _report_callback,
            pattern=(
                f"^({CALLBACK_REPORT_TODAY}|{CALLBACK_REPORT_WEEK}|{CALLBACK_REPORT_MONTH}|"
                f"{CALLBACK_REPORT_INCOME_CATEGORIES}|{CALLBACK_REPORT_EXPENSE_CATEGORIES}|"
                f"{CALLBACK_REPORT_INVESTMENT}|{CALLBACK_REPORT_BACK_TO_MENU}|"
                f"{CALLBACK_REPORT_INCOME_LOG_PREFIX}\\d+|{CALLBACK_REPORT_EXPENSE_LOG_PREFIX}\\d+)$"
            ),
        ),
        MessageHandler(filters.TEXT & ~filters.COMMAND, _quick_input_message),
    ]


async def _start_or_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or update.effective_message is None:
        return

    connection = _connection(context)
    await _db_call(
        register_start_user,
        connection,
        telegram_user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    text, reply_markup = build_start_response(user.first_name)
    await update.effective_message.reply_text(text, reply_markup=reply_markup)


async def _quick_input_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None or message.text is None:
        return

    db_user = await _db_call(
        register_start_user,
        _connection(context),
        telegram_user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    today = today_in(db_user.timezone)

    manual_income_response = await _db_call(
        handle_manual_income_amount_text,
        message.text,
        telegram_user_id=user.id,
        pending_store=_pending_store(context),
        today=today,
    )
    if manual_income_response is not None:
        await message.reply_text(manual_income_response.text, reply_markup=manual_income_response.reply_markup)
        return

    manual_expense_response = await _db_call(
        handle_manual_expense_amount_text,
        message.text,
        telegram_user_id=user.id,
        pending_store=_pending_store(context),
        today=today,
    )
    if manual_expense_response is not None:
        await message.reply_text(manual_expense_response.text, reply_markup=manual_expense_response.reply_markup)
        return

    manual_investment_response = await _db_call(
        handle_manual_investment_amount_text,
        message.text,
        telegram_user_id=user.id,
        pending_store=_pending_store(context),
        today=today,
    )
    if manual_investment_response is not None:
        await message.reply_text(
            manual_investment_response.text,
            reply_markup=manual_investment_response.reply_markup,
        )
        return

    transaction_edit_response = await _db_call(
        handle_transaction_edit_text,
        message.text,
        connection=_connection(context),
        user_id=db_user.id,
        telegram_user_id=user.id,
        pending_store=_pending_store(context),
    )
    if transaction_edit_response is not None:
        await message.reply_text(
            transaction_edit_response.text,
            reply_markup=transaction_edit_response.reply_markup,
        )
        return

    response = await _db_call(
        handle_quick_input_text,
        message.text,
        telegram_user_id=user.id,
        pending_store=_pending_store(context),
        today=today,
    )
    if response is None:
        return
    await message.reply_text(response.text, reply_markup=response.reply_markup)


async def _manual_income_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None or query.data is None:
        return

    await query.answer()
    db_user = await _db_call(
        register_start_user,
        _connection(context),
        telegram_user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    response = await _db_call(
        handle_manual_income_callback,
        query.data,
        connection=_connection(context),
        user_id=db_user.id,
        telegram_user_id=user.id,
        pending_store=_pending_store(context),
    )
    if response is None:
        return
    await query.edit_message_text(text=response.text, reply_markup=response.reply_markup)


async def _manual_expense_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None or query.data is None:
        return

    await query.answer()
    db_user = await _db_call(
        register_start_user,
        _connection(context),
        telegram_user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    response = await _db_call(
        handle_manual_expense_callback,
        query.data,
        connection=_connection(context),
        user_id=db_user.id,
        telegram_user_id=user.id,
        pending_store=_pending_store(context),
    )
    if response is None:
        return
    await query.edit_message_text(text=response.text, reply_markup=response.reply_markup)


async def _manual_investment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None or query.data is None:
        return

    await query.answer()
    db_user = await _db_call(
        register_start_user,
        _connection(context),
        telegram_user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    response = await _db_call(
        handle_manual_investment_callback,
        query.data,
        connection=_connection(context),
        user_id=db_user.id,
        telegram_user_id=user.id,
        pending_store=_pending_store(context),
    )
    if response is None:
        return
    await query.edit_message_text(text=response.text, reply_markup=response.reply_markup)


async def _transactions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None or query.data is None:
        return

    await query.answer()
    db_user = await _db_call(
        register_start_user,
        _connection(context),
        telegram_user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    response = await _db_call(
        handle_transactions_callback,
        query.data,
        connection=_connection(context),
        user_id=db_user.id,
        telegram_user_id=user.id,
        pending_store=_pending_store(context),
    )
    if response is None:
        return
    await query.edit_message_text(text=response.text, reply_markup=response.reply_markup)


async def _quick_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None or query.data is None:
        return

    await query.answer()
    db_user = await _db_call(
        register_start_user,
        _connection(context),
        telegram_user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    response = await _db_call(
        handle_quick_confirm_callback,
        query.data,
        connection=_connection(context),
        user_id=db_user.id,
        telegram_user_id=user.id,
        pending_store=_pending_store(context),
    )
    if response is None:
        return
    await query.edit_message_text(text=response.text, reply_markup=response.reply_markup)


async def _today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_period_report(update, context, "today")


async def _week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_period_report(update, context, "week")


async def _month_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_period_report(update, context, "month")


async def _report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    response = await _db_call(
        build_report_menu_response,)
    await update.effective_message.reply_text(response.text, reply_markup=response.reply_markup)


async def _riwayat_pemasukan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_transaction_log(update, context, "income", page=1)


async def _riwayat_pengeluaran_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_transaction_log(update, context, "expense", page=1)


async def _help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(build_help_text())


async def _report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None or query.data is None:
        return

    await query.answer()
    db_user = await _db_call(
        register_start_user,
        _connection(context),
        telegram_user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    today = today_in(db_user.timezone)

    if query.data == CALLBACK_REPORT_TODAY:
        response = await _db_call(
            build_period_report_response,
            "today", connection=_connection(context), user_id=db_user.id, current_date=today
        )
    elif query.data == CALLBACK_REPORT_WEEK:
        response = await _db_call(
            build_period_report_response,
            "week", connection=_connection(context), user_id=db_user.id, current_date=today
        )
    elif query.data == CALLBACK_REPORT_MONTH:
        response = await _db_call(
            build_period_report_response,
            "month", connection=_connection(context), user_id=db_user.id, current_date=today
        )
    elif query.data == CALLBACK_REPORT_INCOME_CATEGORIES:
        response = await _db_call(
            build_category_report_response,
            "income", connection=_connection(context), user_id=db_user.id, current_date=today
        )
    elif query.data == CALLBACK_REPORT_EXPENSE_CATEGORIES:
        response = await _db_call(
            build_category_report_response,
            "expense", connection=_connection(context), user_id=db_user.id, current_date=today
        )
    elif query.data == CALLBACK_REPORT_BACK_TO_MENU:
        response = await _db_call(
            build_report_menu_response,)
    elif query.data.startswith(CALLBACK_REPORT_INCOME_LOG_PREFIX):
        response = await _db_call(
            build_transaction_log_response,
            "income",
            connection=_connection(context),
            user_id=db_user.id,
            page=parse_report_page(query.data, CALLBACK_REPORT_INCOME_LOG_PREFIX),
        )
    elif query.data.startswith(CALLBACK_REPORT_EXPENSE_LOG_PREFIX):
        response = await _db_call(
            build_transaction_log_response,
            "expense",
            connection=_connection(context),
            user_id=db_user.id,
            page=parse_report_page(query.data, CALLBACK_REPORT_EXPENSE_LOG_PREFIX),
        )
    else:
        response = await _db_call(
            build_investment_report_response,
            connection=_connection(context), user_id=db_user.id, current_date=today
        )

    await query.edit_message_text(text=response.text, reply_markup=response.reply_markup)


async def _send_period_report(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    period: str,
) -> None:
    user = update.effective_user
    if user is None or update.effective_message is None:
        return

    db_user = await _db_call(
        register_start_user,
        _connection(context),
        telegram_user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    response = await _db_call(
        build_period_report_response,
        period,
        connection=_connection(context),
        user_id=db_user.id,
        current_date=today_in(db_user.timezone),
    )
    await update.effective_message.reply_text(response.text, reply_markup=response.reply_markup)


async def _send_transaction_log(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    transaction_type: str,
    *,
    page: int,
) -> None:
    user = update.effective_user
    if user is None or update.effective_message is None:
        return

    db_user = await _db_call(
        register_start_user,
        _connection(context),
        telegram_user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )
    response = await _db_call(
        build_transaction_log_response,
        transaction_type,
        connection=_connection(context),
        user_id=db_user.id,
        page=page,
    )
    await update.effective_message.reply_text(response.text, reply_markup=response.reply_markup)


_DB_LOCK = threading.Lock()


async def _db_call(function: Callable[..., object], /, *args: object, **kwargs: object) -> object:
    """Run synchronous SQLite work off the event loop.

    The bot shares one connection, so every DB call is serialized by a lock.
    """

    def run() -> object:
        with _DB_LOCK:
            return function(*args, **kwargs)

    return await asyncio.to_thread(run)


def _with_db_transaction(callback: Callable[..., object]) -> Callable[..., object]:
    """Commit one handler's writes, roll back on failure."""

    @functools.wraps(callback)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        connection = _connection(context)
        try:
            await callback(update, context)  # type: ignore[misc]
        except BaseException:
            with _DB_LOCK:
                connection.rollback()
            raise
        else:
            with _DB_LOCK:
                connection.commit()

    return wrapped


def _committing_handlers(handlers: list[BaseHandler]) -> list[BaseHandler]:
    """Attach the transaction wrapper to every handler callback."""

    for handler in handlers:
        handler.callback = _with_db_transaction(handler.callback)  # type: ignore[method-assign]
    return handlers


def _connection(context: ContextTypes.DEFAULT_TYPE) -> sqlite3.Connection:
    return context.application.bot_data["connection"]


def _pending_store(context: ContextTypes.DEFAULT_TYPE) -> PendingConfirmationStore:
    return context.application.bot_data["pending_store"]
