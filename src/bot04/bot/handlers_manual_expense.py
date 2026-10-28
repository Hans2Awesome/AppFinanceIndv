"""Manual expense flow. Thin wrapper over :mod:`bot04.bot.handlers_manual`."""

from __future__ import annotations

import sqlite3
from datetime import date

from bot04.bot.handlers_manual import (
    ManualFlow,
    ManualResponse,
    handle_manual_amount_text,
    handle_manual_callback,
)
from bot04.services.pending_store import PendingConfirmationStore

CALLBACK_MANUAL_EXPENSE_START = "add_expense"
CALLBACK_MANUAL_EXPENSE_CATEGORY_PREFIX = "manual_expense_category:"
CALLBACK_MANUAL_EXPENSE_CANCEL = "manual_expense_cancel"

ManualExpenseResponse = ManualResponse

_EXPENSE_FLOW = ManualFlow(
    transaction_type="expense",
    start_callback=CALLBACK_MANUAL_EXPENSE_START,
    category_prefix=CALLBACK_MANUAL_EXPENSE_CATEGORY_PREFIX,
    cancel_callback=CALLBACK_MANUAL_EXPENSE_CANCEL,
    choose_prompt="Pilih kategori pengeluaran:",
    cancel_text="❌ Input pengeluaran dibatalkan.",
    missing_category_text="Kategori pengeluaran tidak ditemukan. Silakan mulai lagi dari menu.",
    amount_prompt=lambda name: (
        f"Masukkan nominal pengeluaran untuk kategori {name}.\n"
        "Contoh: 25000 atau Rp25.000"
    ),
    invalid_amount_text="Nominal belum ditemukan. Masukkan nominal, contoh: 25000",
)


def handle_manual_expense_callback(
    callback_data: str,
    *,
    connection: sqlite3.Connection,
    user_id: int,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
) -> ManualExpenseResponse | None:
    """Handle manual expense category/cancel callbacks."""

    return handle_manual_callback(
        _EXPENSE_FLOW,
        callback_data,
        connection=connection,
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        pending_store=pending_store,
    )


def handle_manual_expense_amount_text(
    text: str,
    *,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
    today: date | None = None,
) -> ManualExpenseResponse | None:
    """Read a nominal for the currently selected manual expense category."""

    return handle_manual_amount_text(
        _EXPENSE_FLOW,
        text,
        telegram_user_id=telegram_user_id,
        pending_store=pending_store,
        today=today,
    )