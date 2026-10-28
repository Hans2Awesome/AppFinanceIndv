"""Generic manual income/expense/investment entry flow for Bot04.

One implementation serves all three transaction types. The per-type modules in
this package stay as thin aliases so imports and callback names keep working.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot04.bot.handlers_quick_input import build_quick_confirmation_keyboard
from bot04.services.pending_store import PendingConfirmationStore
from bot04.services.transaction_preview import format_transaction_preview
from finance_core.db.categories import list_categories
from finance_core.services.money_parser import MoneyParseError, parse_money
from finance_core.services.quick_input_parser import QuickInputResult

_AMOUNT_TOKEN_PATTERN = re.compile(
    r"(?i)(?:rp\s*)?\d+(?:[.,]\d+)*(?:(?:\s*(?:rb|ribu|jt|juta)\b)|(?:\s*k\b))?"
)


@dataclass(frozen=True)
class ManualResponse:
    """Telegram message/edit payload returned by a manual entry flow."""

    text: str
    reply_markup: InlineKeyboardMarkup | None


@dataclass(frozen=True)
class ManualFlow:
    """Static strings and callbacks that differ between the three flows."""

    transaction_type: str
    start_callback: str
    category_prefix: str
    cancel_callback: str
    choose_prompt: str
    cancel_text: str
    missing_category_text: str
    amount_prompt: Callable[[str], str]
    invalid_amount_text: str
    asset_aliases: dict[str, list[str]] = field(default_factory=dict)
    default_asset: Callable[[str], str | None] | None = None


def handle_manual_callback(
    flow: ManualFlow,
    callback_data: str,
    *,
    connection: sqlite3.Connection,
    user_id: int,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
) -> ManualResponse | None:
    """Handle the start, cancel, and category callbacks for one flow."""

    if callback_data == flow.start_callback:
        pending_store.clear(telegram_user_id=telegram_user_id)
        return ManualResponse(
            text=flow.choose_prompt,
            reply_markup=_build_category_keyboard(flow, connection, user_id=user_id),
        )

    if callback_data == flow.cancel_callback:
        pending_store.clear(telegram_user_id=telegram_user_id)
        return ManualResponse(text=flow.cancel_text, reply_markup=None)

    if callback_data.startswith(flow.category_prefix):
        category_id = _parse_category_callback(flow, callback_data)
        category_name = _category_name(
            connection,
            user_id=user_id,
            category_type=flow.transaction_type,
            category_id=category_id,
        )
        if category_name is None:
            return ManualResponse(text=flow.missing_category_text, reply_markup=None)

        pending_store.set(
            telegram_user_id=telegram_user_id,
            preview=_draft(flow, category_name=category_name),
        )
        return ManualResponse(text=flow.amount_prompt(category_name), reply_markup=None)

    return None


def handle_manual_amount_text(
    flow: ManualFlow,
    text: str,
    *,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
    today: date | None = None,
) -> ManualResponse | None:
    """Read a nominal for the currently selected category of one flow."""

    draft = pending_store.get(telegram_user_id=telegram_user_id)
    if (
        draft is None
        or draft.type != flow.transaction_type
        or draft.category_name is None
        or draft.amount is not None
    ):
        return None

    try:
        amount = parse_money(text)
    except MoneyParseError:
        return ManualResponse(text=flow.invalid_amount_text, reply_markup=None)

    asset_name = _detect_asset_name(flow, text, fallback=draft.asset_name)
    completed_preview = QuickInputResult(
        type=flow.transaction_type,
        category_name=draft.category_name,
        amount=amount,
        note=_build_note(flow, text, asset_name=asset_name),
        asset_name=asset_name,
        transaction_date=today or date.today(),
        confidence=1.0,
        needs_review=False,
        original_text=text.strip(),
        error=None,
    )
    pending_store.set(telegram_user_id=telegram_user_id, preview=completed_preview)
    return ManualResponse(
        text=format_transaction_preview(completed_preview),
        reply_markup=build_quick_confirmation_keyboard(),
    )


def _build_category_keyboard(
    flow: ManualFlow,
    connection: sqlite3.Connection,
    *,
    user_id: int,
) -> InlineKeyboardMarkup:
    categories = sorted(
        list_categories(connection, user_id, category_type=flow.transaction_type),
        key=lambda category: category.id,
    )
    buttons = [
        InlineKeyboardButton(
            category.name,
            callback_data=f"{flow.category_prefix}{category.id}",
        )
        for category in categories
    ]
    keyboard_rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    keyboard_rows.append([InlineKeyboardButton("❌ Batal", callback_data=flow.cancel_callback)])
    return InlineKeyboardMarkup(keyboard_rows)


def _parse_category_callback(flow: ManualFlow, callback_data: str) -> int:
    value = callback_data.removeprefix(flow.category_prefix)
    try:
        return int(value)
    except ValueError:
        return -1


def _category_name(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    category_type: str,
    category_id: int,
) -> str | None:
    for category in list_categories(connection, user_id, category_type=category_type):
        if category.id == category_id:
            return category.name
    return None


def _draft(flow: ManualFlow, *, category_name: str) -> QuickInputResult:
    asset_name = flow.default_asset(category_name) if flow.default_asset else None
    return QuickInputResult(
        type=flow.transaction_type,
        category_name=category_name,
        amount=None,
        note="",
        asset_name=asset_name,
        transaction_date=None,
        confidence=1.0,
        needs_review=False,
        original_text="",
        error=None,
    )


def _detect_asset_name(flow: ManualFlow, text: str, *, fallback: str | None) -> str | None:
    lowered = text.lower()
    for asset_name, aliases in flow.asset_aliases.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", lowered):
                return asset_name
    return fallback


def _build_note(flow: ManualFlow, text: str, *, asset_name: str | None) -> str:
    cleaned = _AMOUNT_TOKEN_PATTERN.sub(" ", text, count=1)
    if asset_name in flow.asset_aliases:
        for alias in flow.asset_aliases[asset_name]:
            cleaned = re.sub(rf"(?i)\b{re.escape(alias)}\b", " ", cleaned)
    return " ".join(cleaned.split())