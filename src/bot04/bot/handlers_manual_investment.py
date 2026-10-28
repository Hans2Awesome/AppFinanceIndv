"""Manual investment flow. Thin wrapper over :mod:`bot04.bot.handlers_manual`."""

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

CALLBACK_MANUAL_INVESTMENT_START = "add_investment"
CALLBACK_MANUAL_INVESTMENT_CATEGORY_PREFIX = "manual_investment_category:"
CALLBACK_MANUAL_INVESTMENT_CANCEL = "manual_investment_cancel"

ManualInvestmentResponse = ManualResponse

_ASSET_ALIASES: dict[str, list[str]] = {
    "BTC": ["btc", "bitcoin"],
    "ETH": ["eth", "ethereum"],
    "Emas": ["emas", "gold", "antam"],
}


def _default_asset_name(category_name: str) -> str | None:
    if category_name in {"Crypto", "Emas"}:
        return category_name
    return None


_INVESTMENT_FLOW = ManualFlow(
    transaction_type="investment",
    start_callback=CALLBACK_MANUAL_INVESTMENT_START,
    category_prefix=CALLBACK_MANUAL_INVESTMENT_CATEGORY_PREFIX,
    cancel_callback=CALLBACK_MANUAL_INVESTMENT_CANCEL,
    choose_prompt="Pilih jenis investasi:",
    cancel_text="❌ Input investasi dibatalkan.",
    missing_category_text="Kategori investasi tidak ditemukan. Silakan mulai lagi dari menu.",
    amount_prompt=lambda name: (
        f"Masukkan nominal investasi untuk kategori {name}.\n"
        "Contoh: 100000 atau Rp100.000"
    ),
    invalid_amount_text="Nominal belum ditemukan. Masukkan nominal, contoh: 100000",
    asset_aliases=_ASSET_ALIASES,
    default_asset=_default_asset_name,
)


def handle_manual_investment_callback(
    callback_data: str,
    *,
    connection: sqlite3.Connection,
    user_id: int,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
) -> ManualInvestmentResponse | None:
    """Handle manual investment category/cancel callbacks."""

    return handle_manual_callback(
        _INVESTMENT_FLOW,
        callback_data,
        connection=connection,
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        pending_store=pending_store,
    )


def handle_manual_investment_amount_text(
    text: str,
    *,
    telegram_user_id: int,
    pending_store: PendingConfirmationStore,
    today: date | None = None,
) -> ManualInvestmentResponse | None:
    """Read a nominal for the currently selected manual investment category."""

    return handle_manual_amount_text(
        _INVESTMENT_FLOW,
        text,
        telegram_user_id=telegram_user_id,
        pending_store=pending_store,
        today=today,
    )