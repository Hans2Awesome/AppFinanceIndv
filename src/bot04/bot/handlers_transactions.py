"""Recent transaction list/edit/delete handler helpers for Bot04 Telegram bot."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot04.services.pending_store import PendingConfirmationStore
from finance_core.db.transactions import (
    Transaction,
    delete_transaction,
    get_transaction_by_id,
    list_transactions,
    update_transaction,
)
from finance_core.domain import transaction_type_label
from finance_core.services.money_parser import MoneyParseError, parse_money
from finance_core.services.quick_input_parser import QuickInputResult

CALLBACK_TRANSACTIONS_RECENT = "transactions_recent"
CALLBACK_TRANSACTION_EDIT_PREFIX = "transaction_edit:"
CALLBACK_TRANSACTION_DELETE_PREFIX = "transaction_delete:"
CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX = "transaction_delete_confirm:"
CALLBACK_TRANSACTION_DELETE_CANCEL = "transaction_delete_cancel"
_EDIT_PENDING_PREFIX = "edit_transaction:"

_AMOUNT_TOKEN_PATTERN = re.compile(
    r"(?i)(?:rp\s*)?\d+(?:[.,]\d+)*(?:(?:\s*(?:rb|ribu|jt|juta)\b)|(?:\s*k\b))?"
)


@dataclass(frozen=True)
class TransactionHandlerResponse:
    """Telegram message/edit payload for transaction management helpers."""

    text: str
    reply_markup: InlineKeyboardMarkup | None


def handle_transactions_callback(
    callback_data: str,
    *,
    connection: sqlite3.Connection,
    user_id: int,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
) -> TransactionHandlerResponse | None:
    """Handle recent/list, edit, and delete callbacks."""

    if callback_data == CALLBACK_TRANSACTIONS_RECENT:
        return _build_recent_transactions_response(connection, user_id=user_id)

    if callback_data.startswith(CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX):
        transaction_id = _parse_prefixed_id(callback_data, CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX)
        deleted = delete_transaction(connection, user_id=user_id, transaction_id=transaction_id)
        if not deleted:
            return TransactionHandlerResponse(text="Transaksi tidak ditemukan.", reply_markup=None)
        return TransactionHandlerResponse(text="✅ Transaksi berhasil dihapus.", reply_markup=None)

    if callback_data.startswith(CALLBACK_TRANSACTION_DELETE_PREFIX):
        transaction_id = _parse_prefixed_id(callback_data, CALLBACK_TRANSACTION_DELETE_PREFIX)
        transaction = _fetch_owned_transaction(connection, user_id=user_id, transaction_id=transaction_id)
        if transaction is None:
            return TransactionHandlerResponse(text="Transaksi tidak ditemukan.", reply_markup=None)
        return TransactionHandlerResponse(
            text=f"Yakin hapus transaksi {_format_transaction_short(transaction)}?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Ya, hapus",
                            callback_data=f"{CALLBACK_TRANSACTION_DELETE_CONFIRM_PREFIX}{transaction.id}",
                        ),
                        InlineKeyboardButton("❌ Batal", callback_data=CALLBACK_TRANSACTION_DELETE_CANCEL),
                    ]
                ]
            ),
        )

    if callback_data == CALLBACK_TRANSACTION_DELETE_CANCEL:
        return TransactionHandlerResponse(text="❌ Hapus transaksi dibatalkan.", reply_markup=None)

    if callback_data.startswith(CALLBACK_TRANSACTION_EDIT_PREFIX):
        transaction_id = _parse_prefixed_id(callback_data, CALLBACK_TRANSACTION_EDIT_PREFIX)
        transaction = _fetch_owned_transaction(connection, user_id=user_id, transaction_id=transaction_id)
        if transaction is None:
            return TransactionHandlerResponse(text="Transaksi tidak ditemukan.", reply_markup=None)
        pending_store.set(
            telegram_user_id=telegram_user_id,
            preview=_edit_pending(transaction_id=transaction.id),
        )
        return TransactionHandlerResponse(
            text="Kirim nominal/catatan baru untuk transaksi ini.\nContoh: 30000 kopi sore",
            reply_markup=None,
        )

    return None


def handle_transaction_edit_text(
    text: str,
    *,
    connection: sqlite3.Connection,
    user_id: int,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
) -> TransactionHandlerResponse | None:
    """Apply amount/note text to a pending transaction edit."""

    pending = pending_store.get(telegram_user_id=telegram_user_id)
    if pending is None or not pending.original_text.startswith(_EDIT_PENDING_PREFIX):
        return None

    transaction_id = _parse_prefixed_id(pending.original_text, _EDIT_PENDING_PREFIX)
    transaction = _fetch_owned_transaction(connection, user_id=user_id, transaction_id=transaction_id)
    if transaction is None:
        pending_store.clear(telegram_user_id=telegram_user_id)
        return TransactionHandlerResponse(text="Transaksi tidak ditemukan.", reply_markup=None)

    try:
        amount = parse_money(text)
    except MoneyParseError:
        return TransactionHandlerResponse(
            text="Nominal belum ditemukan. Kirim contoh: 30000 kopi sore",
            reply_markup=None,
        )

    note = _build_note(text) or None
    updated = update_transaction(
        connection,
        user_id=user_id,
        transaction_id=transaction.id,
        amount=amount,
        category_id=transaction.category_id,
        transaction_date=transaction.transaction_date,
        note=note,
    )
    pending_store.clear(telegram_user_id=telegram_user_id)
    if updated is None:
        return TransactionHandlerResponse(text="Transaksi tidak ditemukan.", reply_markup=None)

    return TransactionHandlerResponse(
        text=f"✅ Transaksi berhasil diupdate menjadi {_format_rupiah(updated.amount)} — {updated.note or '-'}.",
        reply_markup=None,
    )


def _build_recent_transactions_response(
    connection: sqlite3.Connection,
    *,
    user_id: int,
) -> TransactionHandlerResponse:
    transactions = _recent_transactions(connection, user_id=user_id, limit=5)
    if not transactions:
        return TransactionHandlerResponse(text="Belum ada transaksi.", reply_markup=None)

    lines = ["Transaksi terakhir:"]
    keyboard_rows: list[list[InlineKeyboardButton]] = []
    for index, transaction in enumerate(transactions, start=1):
        lines.append(f"{index}. {_format_transaction_line(transaction)}")
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    f"✏️ Edit {index}",
                    callback_data=f"{CALLBACK_TRANSACTION_EDIT_PREFIX}{transaction.id}",
                ),
                InlineKeyboardButton(
                    f"🗑 Hapus {index}",
                    callback_data=f"{CALLBACK_TRANSACTION_DELETE_PREFIX}{transaction.id}",
                ),
            ]
        )

    return TransactionHandlerResponse(
        text="\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )


def _recent_transactions(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    limit: int,
) -> list[Transaction]:
    return list_transactions(connection, user_id=user_id, limit=limit)


def _fetch_owned_transaction(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    transaction_id: int,
) -> Transaction | None:
    return get_transaction_by_id(
        connection,
        user_id=user_id,
        transaction_id=transaction_id,
    )


def _edit_pending(*, transaction_id: int) -> QuickInputResult:
    return QuickInputResult(
        type=None,
        category_name=None,
        amount=None,
        note="",
        asset_name=None,
        transaction_date=None,
        confidence=1.0,
        needs_review=False,
        original_text=f"{_EDIT_PENDING_PREFIX}{transaction_id}",
        error=None,
    )


def _parse_prefixed_id(value: str, prefix: str) -> int:
    try:
        return int(value.removeprefix(prefix))
    except ValueError:
        return -1


def _format_transaction_line(transaction: Transaction) -> str:
    return (
        f"{transaction.transaction_date} — {transaction_type_label(transaction.type)} "
        f"{_format_rupiah(transaction.amount)} — {transaction.note or '-'}"
    )


def _format_transaction_short(transaction: Transaction) -> str:
    return f"{_format_rupiah(transaction.amount)} — {transaction.note or '-'}"


def _format_rupiah(amount: int) -> str:
    return f"Rp{amount:,}".replace(",", ".")


def _build_note(text: str) -> str:
    return " ".join(_AMOUNT_TOKEN_PATTERN.sub(" ", text, count=1).split())
