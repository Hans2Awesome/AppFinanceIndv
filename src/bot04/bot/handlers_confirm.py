"""Quick input confirmation callback handler helpers for Bot04 Telegram bot."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from telegram import InlineKeyboardMarkup

from bot04.bot.handlers_quick_input import CALLBACK_QUICK_CANCEL, CALLBACK_QUICK_SAVE
from bot04.services.pending_store import PendingConfirmationStore
from finance_core.domain import transaction_type_label
from finance_core.services.transaction_service import save_confirmed_transaction


@dataclass(frozen=True)
class ConfirmHandlerResponse:
    """Edited message payload returned by confirmation callback logic."""

    text: str
    reply_markup: InlineKeyboardMarkup | None


def handle_quick_confirm_callback(
    callback_data: str,
    *,
    connection: sqlite3.Connection,
    user_id: int,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
) -> ConfirmHandlerResponse | None:
    """Handle quick input save/cancel callbacks.

    Returns None for unrelated callback data so later callback handlers can process
    their own buttons.
    """

    if callback_data not in {CALLBACK_QUICK_SAVE, CALLBACK_QUICK_CANCEL}:
        return None

    pending_preview = pending_store.get(telegram_user_id=telegram_user_id)
    if pending_preview is None:
        return ConfirmHandlerResponse(
            text="Preview transaksi sudah expired atau tidak ditemukan. Silakan ketik transaksi lagi.",
            reply_markup=None,
        )

    if callback_data == CALLBACK_QUICK_CANCEL:
        pending_store.clear(telegram_user_id=telegram_user_id)
        return ConfirmHandlerResponse(text="❌ Transaksi dibatalkan.", reply_markup=None)

    summary = save_confirmed_transaction(
        connection,
        user_id=user_id,
        preview=pending_preview,
    )
    pending_store.clear(telegram_user_id=telegram_user_id)
    return ConfirmHandlerResponse(
        text=(
            "✅ Transaksi berhasil disimpan.\n\n"
            f"{transaction_type_label(summary.type)} {summary.category_name} "
            f"{_format_rupiah(summary.amount)} sudah tercatat."
        ),
        reply_markup=None,
    )


def _format_rupiah(amount: int) -> str:
    return f"Rp{amount:,}".replace(",", ".")
