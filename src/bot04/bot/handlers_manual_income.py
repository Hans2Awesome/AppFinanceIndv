"""Manual income flow. Thin wrapper over :mod:`bot04.bot.handlers_manual`."""

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

CALLBACK_MANUAL_INCOME_START = "add_income"
CALLBACK_MANUAL_INCOME_CATEGORY_PREFIX = "manual_income_category:"
CALLBACK_MANUAL_INCOME_CANCEL = "manual_income_cancel"

ManualIncomeResponse = ManualResponse

_INCOME_FLOW = ManualFlow(
    transaction_type="income",
    start_callback=CALLBACK_MANUAL_INCOME_START,
    category_prefix=CALLBACK_MANUAL_INCOME_CATEGORY_PREFIX,
    cancel_callback=CALLBACK_MANUAL_INCOME_CANCEL,
    choose_prompt="Pilih kategori pemasukan:",
    cancel_text="❌ Input pemasukan dibatalkan.",
    missing_category_text="Kategori pemasukan tidak ditemukan. Silakan mulai lagi dari menu.",
    amount_prompt=lambda name: (
        f"Masukkan nominal pemasukan untuk kategori {name}.\n"
        "Contoh: 5000000 atau Rp5.000.000"
    ),
    invalid_amount_text="Nominal belum ditemukan. Masukkan nominal, contoh: 5000000",
)


def handle_manual_income_callback(
    callback_data: str,
    *,
    connection: sqlite3.Connection,
    user_id: int,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
) -> ManualIncomeResponse | None:
    """Handle manual income category/cancel callbacks."""

    return handle_manual_callback(
        _INCOME_FLOW,
        callback_data,
        connection=connection,
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        pending_store=pending_store,
    )


def handle_manual_income_amount_text(
    text: str,
    *,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
    today: date | None = None,
) -> ManualIncomeResponse | None:
    """Read a nominal for the currently selected manual income category."""

    return handle_manual_amount_text(
        _INCOME_FLOW,
        text,
        telegram_user_id=telegram_user_id,
        pending_store=pending_store,
        today=today,
    )