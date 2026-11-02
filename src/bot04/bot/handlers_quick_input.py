"""Quick input message handler helpers for Bot04 Telegram bot."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot04.services.pending_store import PendingConfirmationStore
from bot04.services.transaction_preview import format_transaction_preview
from finance_core.db.categories import list_categories
from finance_core.services.quick_input_parser import parse_quick_input

CALLBACK_QUICK_SAVE = "quick_save"
CALLBACK_QUICK_EDIT = "quick_edit"
CALLBACK_QUICK_CANCEL = "quick_cancel"

_HELP_EXAMPLES = """Contoh input cepat:
- makan 25000
- gaji 5000000
- btc 100000 dca mingguan"""


@dataclass(frozen=True)
class QuickInputHandlerResponse:
    """Message payload returned by quick input handler logic."""

    text: str
    reply_markup: InlineKeyboardMarkup | None


def handle_quick_input_text(
    text: str,
    *,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
    today: date | None = None,
    connection: sqlite3.Connection | None = None,
    user_id: int | None = None,
) -> QuickInputHandlerResponse | None:
    """Parse free text transaction input and return response payload.

    Commands are ignored so command handlers can process them separately.
    """

    stripped_text = text.strip()
    if stripped_text.startswith("/"):
        return None

    custom_categories = None
    if connection is not None and user_id is not None:
        custom_categories = [
            (row.type, row.name)
            for row in list_categories(connection, user_id=user_id)
            if row.is_default == 0
        ]

    parsed = parse_quick_input(
        stripped_text, today=today, custom_categories=custom_categories
    )
    if parsed.error:
        return QuickInputHandlerResponse(
            text=f"{parsed.error}\n\n{_HELP_EXAMPLES}",
            reply_markup=None,
        )

    pending_store.set(telegram_user_id=telegram_user_id, preview=parsed)
    return QuickInputHandlerResponse(
        text=format_transaction_preview(parsed),
        reply_markup=build_quick_confirmation_keyboard(),
    )


def build_quick_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for confirming quick input previews."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Simpan", callback_data=CALLBACK_QUICK_SAVE),
                InlineKeyboardButton("✏️ Edit", callback_data=CALLBACK_QUICK_EDIT),
                InlineKeyboardButton("❌ Batal", callback_data=CALLBACK_QUICK_CANCEL),
            ]
        ]
    )
