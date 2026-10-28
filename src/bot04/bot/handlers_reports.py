"""Report command handler helpers for Bot04 Telegram bot."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot04.reports.formatter import (
    format_category_report,
    format_investment_report,
    format_period_report,
    format_transaction_log_report,
)
from finance_core.db.transactions import (
    Transaction,
    count_transactions_by_type,
    list_transactions_by_type,
    list_transactions_in_range,
)
from finance_core.domain import transaction_type_label
from finance_core.reports.aggregator import (
    aggregate_by_category,
    aggregate_transactions,
)
from finance_core.reports.date_ranges import (
    DateRange,
    month_range,
    today_range,
    week_range,
)

CALLBACK_REPORT_TODAY = "report_today"
CALLBACK_REPORT_WEEK = "report_week"
CALLBACK_REPORT_MONTH = "report_month"
CALLBACK_REPORT_INCOME_CATEGORIES = "report_income_categories"
CALLBACK_REPORT_EXPENSE_CATEGORIES = "report_expense_categories"
CALLBACK_REPORT_INVESTMENT = "report_investment"
LOG_PAGE_SIZE = 10
CALLBACK_REPORT_INCOME_LOG_PREFIX = "report_income_log:"
CALLBACK_REPORT_EXPENSE_LOG_PREFIX = "report_expense_log:"
CALLBACK_REPORT_BACK_TO_MENU = "report_menu"


@dataclass(frozen=True)
class ReportMenuResponse:
    """Telegram message payload for report handlers."""

    text: str
    reply_markup: InlineKeyboardMarkup | None


def build_period_report_response(
    period: str,
    *,
    connection: sqlite3.Connection,
    user_id: int,
    current_date: date,
) -> ReportMenuResponse:
    """Build today, week, or month report text for one user."""

    title, date_range = _period_title_and_range(period, current_date)
    transactions = _transactions_for_range(connection, user_id=user_id, date_range=date_range)
    summary = aggregate_transactions(transactions)
    return ReportMenuResponse(
        text=format_period_report(title=title, date_range=date_range, summary=summary),
        reply_markup=None,
    )


def build_report_menu_response() -> ReportMenuResponse:
    """Build a report menu with choices for /report."""

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📅 Hari Ini", callback_data=CALLBACK_REPORT_TODAY),
                InlineKeyboardButton("🗓 Minggu Ini", callback_data=CALLBACK_REPORT_WEEK),
            ],
            [InlineKeyboardButton("📆 Bulan Ini", callback_data=CALLBACK_REPORT_MONTH)],
            [
                InlineKeyboardButton(
                    "🗂 Kategori Pemasukan",
                    callback_data=CALLBACK_REPORT_INCOME_CATEGORIES,
                ),
                InlineKeyboardButton(
                    "🗂 Kategori Pengeluaran",
                    callback_data=CALLBACK_REPORT_EXPENSE_CATEGORIES,
                ),
            ],
            [
                InlineKeyboardButton(
                    "💰 Riwayat Pemasukan",
                    callback_data=f"{CALLBACK_REPORT_INCOME_LOG_PREFIX}1",
                ),
                InlineKeyboardButton(
                    "💸 Riwayat Pengeluaran",
                    callback_data=f"{CALLBACK_REPORT_EXPENSE_LOG_PREFIX}1",
                ),
            ],
            [InlineKeyboardButton("📈 Investasi", callback_data=CALLBACK_REPORT_INVESTMENT)],
        ]
    )
    return ReportMenuResponse(text="Pilih jenis laporan:", reply_markup=keyboard)


def build_category_report_response(
    transaction_type: str,
    *,
    connection: sqlite3.Connection,
    user_id: int,
    current_date: date,
) -> ReportMenuResponse:
    """Build current-month category totals for income or expense."""

    date_range = month_range(current_date)
    transactions = _transactions_for_range(connection, user_id=user_id, date_range=date_range)
    categories, _ = aggregate_by_category(
        transactions,
        category_type=transaction_type,
    )
    return ReportMenuResponse(
        text=format_category_report(
            title=f"Kategori {transaction_type_label(transaction_type)}",
            categories=categories,
        ),
        reply_markup=None,
    )


def build_investment_report_response(
    *,
    connection: sqlite3.Connection,
    user_id: int,
    current_date: date,
) -> ReportMenuResponse:
    """Build current-month investment report for one user."""

    date_range = month_range(current_date)
    transactions = _transactions_for_range(connection, user_id=user_id, date_range=date_range)
    summary = aggregate_transactions(transactions)
    return ReportMenuResponse(text=format_investment_report(summary), reply_markup=None)


def build_transaction_log_response(
    transaction_type: str,
    *,
    connection: sqlite3.Connection,
    user_id: int,
    page: int,
) -> ReportMenuResponse:
    """Build paginated income or expense transaction history for one user."""

    total = count_transactions_by_type(connection, user_id=user_id, transaction_type=transaction_type)
    total_pages = max(1, math.ceil(total / LOG_PAGE_SIZE))
    normalized_page = min(max(page, 1), total_pages)
    transactions = list_transactions_by_type(
        connection,
        user_id=user_id,
        transaction_type=transaction_type,
        limit=LOG_PAGE_SIZE,
        offset=(normalized_page - 1) * LOG_PAGE_SIZE,
    )
    prefix = (
        CALLBACK_REPORT_INCOME_LOG_PREFIX
        if transaction_type == "income"
        else CALLBACK_REPORT_EXPENSE_LOG_PREFIX
    )
    return ReportMenuResponse(
        text=format_transaction_log_report(
            transaction_type=transaction_type,
            transactions=transactions,
            page=normalized_page,
            total_pages=total_pages,
        ),
        reply_markup=_log_pagination_keyboard(prefix=prefix, page=normalized_page, total_pages=total_pages),
    )


def parse_report_page(callback_data: str, prefix: str) -> int:
    """Parse one-based report page from callback data, defaulting to page 1."""

    if not callback_data.startswith(prefix):
        return 1
    try:
        return int(callback_data.removeprefix(prefix))
    except ValueError:
        return 1


def _log_pagination_keyboard(
    *,
    prefix: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Build pagination controls for transaction history reports."""

    rows: list[list[InlineKeyboardButton]] = []
    navigation_row: list[InlineKeyboardButton] = []
    if page > 1:
        navigation_row.append(
            InlineKeyboardButton("⬅️ Sebelumnya", callback_data=f"{prefix}{page - 1}")
        )
    if page < total_pages:
        navigation_row.append(
            InlineKeyboardButton("➡️ Berikutnya", callback_data=f"{prefix}{page + 1}")
        )
    if navigation_row:
        rows.append(navigation_row)
    rows.append([InlineKeyboardButton("🔙 Kembali ke Report", callback_data=CALLBACK_REPORT_BACK_TO_MENU)])
    return InlineKeyboardMarkup(rows)


def _period_title_and_range(period: str, current_date: date) -> tuple[str, DateRange]:
    if period == "today":
        return "Laporan Harian", today_range(current_date)
    if period == "week":
        return "Laporan Mingguan", week_range(current_date)
    if period == "month":
        return "Laporan Bulanan", month_range(current_date)
    raise ValueError(f"Unknown report period: {period}")


def _transactions_for_range(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    date_range: DateRange,
) -> list[Transaction]:
    return list_transactions_in_range(
        connection,
        user_id=user_id,
        start_date=date_range.start_date.isoformat(),
        end_date=date_range.end_date.isoformat(),
    )
