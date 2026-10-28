"""Tests for report command handler helpers."""

from __future__ import annotations

import sqlite3
from datetime import date

from bot04.bot.handlers_reports import (
    CALLBACK_REPORT_BACK_TO_MENU,
    CALLBACK_REPORT_EXPENSE_LOG_PREFIX,
    CALLBACK_REPORT_INCOME_LOG_PREFIX,
    ReportMenuResponse,
    build_category_report_response,
    build_investment_report_response,
    build_period_report_response,
    build_report_menu_response,
    build_transaction_log_response,
)
from finance_core.db.categories import seed_default_categories
from finance_core.db.connection import connect
from finance_core.db.migrations import init_db
from finance_core.db.transactions import create_transaction
from finance_core.db.users import get_or_create_user


def setup_connection() -> sqlite3.Connection:
    connection = connect(":memory:")
    init_db(connection)
    return connection


def setup_user(connection: sqlite3.Connection, telegram_user_id: int = 796529359) -> int:
    user = get_or_create_user(connection, telegram_user_id=telegram_user_id)
    seed_default_categories(connection, user.id)
    return user.id


def category_id(connection: sqlite3.Connection, user_id: int, type: str, name: str) -> int:
    row = connection.execute(
        "SELECT id FROM categories WHERE user_id = ? AND type = ? AND name = ?",
        (user_id, type, name),
    ).fetchone()
    assert row is not None
    return row[0]


def add_transaction(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    type: str,
    category_name: str,
    amount: int,
    transaction_date: str,
    note: str | None = None,
) -> None:
    create_transaction(
        connection,
        user_id=user_id,
        type=type,
        category_id=category_id(connection, user_id, type, category_name),
        amount=amount,
        note=note,
        asset_name="BTC" if type == "investment" else None,
        transaction_date=transaction_date,
    )


def test_build_today_report_response_formats_daily_report_for_user_transactions() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    other_user_id = setup_user(connection, telegram_user_id=123)
    add_transaction(
        connection,
        user_id=user_id,
        type="income",
        category_name="Gaji",
        amount=5_000_000,
        transaction_date="2026-05-30",
    )
    add_transaction(
        connection,
        user_id=user_id,
        type="expense",
        category_name="Makan & Minum",
        amount=25_000,
        transaction_date="2026-05-30",
    )
    add_transaction(
        connection,
        user_id=user_id,
        type="expense",
        category_name="Transportasi",
        amount=15_000,
        transaction_date="2026-05-29",
    )
    add_transaction(
        connection,
        user_id=other_user_id,
        type="expense",
        category_name="Makan & Minum",
        amount=99_000,
        transaction_date="2026-05-30",
    )

    response = build_period_report_response(
        "today",
        connection=connection,
        user_id=user_id,
        current_date=date(2026, 5, 30),
    )

    assert response.text.startswith("📊 Laporan Harian\nPeriode: 30 Mei 2026")
    assert "Pemasukan: Rp5.000.000" in response.text
    assert "Pengeluaran: Rp25.000" in response.text
    assert "Makan & Minum — Rp25.000" in response.text
    assert "Transportasi" not in response.text
    assert "Rp99.000" not in response.text
    assert response.reply_markup is None


def test_build_week_and_month_report_responses_use_expected_period_titles() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)

    week_response = build_period_report_response(
        "week",
        connection=connection,
        user_id=user_id,
        current_date=date(2026, 5, 30),
    )
    month_response = build_period_report_response(
        "month",
        connection=connection,
        user_id=user_id,
        current_date=date(2026, 5, 30),
    )

    assert week_response.text.startswith("📊 Laporan Mingguan\nPeriode: 25 Mei 2026 - 31 Mei 2026")
    assert month_response.text.startswith("📊 Laporan Bulanan\nPeriode: 1 Mei 2026 - 31 Mei 2026")


def test_build_report_menu_response_returns_report_choices_keyboard() -> None:
    response = build_report_menu_response()

    assert response == ReportMenuResponse(
        text="Pilih jenis laporan:",
        reply_markup=response.reply_markup,
    )
    assert response.reply_markup is not None
    assert [[button.text for button in row] for row in response.reply_markup.inline_keyboard] == [
        ["📅 Hari Ini", "🗓 Minggu Ini"],
        ["📆 Bulan Ini"],
        ["🗂 Kategori Pemasukan", "🗂 Kategori Pengeluaran"],
        ["💰 Riwayat Pemasukan", "💸 Riwayat Pengeluaran"],
        ["📈 Investasi"],
    ]
    assert [[button.callback_data for button in row] for row in response.reply_markup.inline_keyboard][3] == [
        f"{CALLBACK_REPORT_INCOME_LOG_PREFIX}1",
        f"{CALLBACK_REPORT_EXPENSE_LOG_PREFIX}1",
    ]


def test_build_category_report_response_formats_income_or_expense_totals() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    add_transaction(
        connection,
        user_id=user_id,
        type="income",
        category_name="Gaji",
        amount=5_000_000,
        transaction_date="2026-05-30",
    )
    add_transaction(
        connection,
        user_id=user_id,
        type="income",
        category_name="Bonus",
        amount=100_000,
        transaction_date="2026-05-30",
    )
    add_transaction(
        connection,
        user_id=user_id,
        type="expense",
        category_name="Makan & Minum",
        amount=25_000,
        transaction_date="2026-05-30",
    )

    response = build_category_report_response(
        "income",
        connection=connection,
        user_id=user_id,
        current_date=date(2026, 5, 30),
    )

    assert response.text == (
        "🗂 Kategori Pemasukan\n"
        "1. Gaji — Rp5.000.000\n"
        "2. Bonus — Rp100.000"
    )


def test_build_transaction_log_response_formats_first_page_with_next_button() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    other_user_id = setup_user(connection, telegram_user_id=123)
    for index in range(12):
        add_transaction(
            connection,
            user_id=user_id,
            type="income",
            category_name="Gaji",
            amount=100_000 + index,
            transaction_date=f"2026-05-{index + 1:02d}",
            note=f"income {index}",
        )
    add_transaction(
        connection,
        user_id=user_id,
        type="expense",
        category_name="Makan & Minum",
        amount=999_000,
        transaction_date="2026-05-31",
        note="wrong type",
    )
    add_transaction(
        connection,
        user_id=other_user_id,
        type="income",
        category_name="Gaji",
        amount=888_000,
        transaction_date="2026-05-31",
        note="other user",
    )

    response = build_transaction_log_response("income", connection=connection, user_id=user_id, page=1)

    assert response.text.startswith(
        "💰 Riwayat Pemasukan\nHalaman 1 dari 2\nUrutan: terbaru dulu\n\n"
        "1. 12 Mei 2026 — Rp100.011\n"
        "   Kategori: Gaji\n"
        "   Catatan: income 11"
    )
    assert "10. 3 Mei 2026 — Rp100.002" in response.text
    assert "Rp100.001" not in response.text
    assert "wrong type" not in response.text
    assert "other user" not in response.text
    assert response.reply_markup is not None
    assert [[button.text for button in row] for row in response.reply_markup.inline_keyboard] == [
        ["➡️ Berikutnya"],
        ["🔙 Kembali ke Report"],
    ]
    assert [[button.callback_data for button in row] for row in response.reply_markup.inline_keyboard] == [
        [f"{CALLBACK_REPORT_INCOME_LOG_PREFIX}2"],
        [CALLBACK_REPORT_BACK_TO_MENU],
    ]


def test_build_transaction_log_response_formats_last_page_with_previous_button() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    for index in range(12):
        add_transaction(
            connection,
            user_id=user_id,
            type="expense",
            category_name="Makan & Minum",
            amount=25_000 + index,
            transaction_date=f"2026-05-{index + 1:02d}",
            note=f"expense {index}",
        )

    response = build_transaction_log_response("expense", connection=connection, user_id=user_id, page=99)

    assert response.text.startswith(
        "💸 Riwayat Pengeluaran\nHalaman 2 dari 2\nUrutan: terbaru dulu\n\n"
        "1. 2 Mei 2026 — Rp25.001"
    )
    assert "2. 1 Mei 2026 — Rp25.000" in response.text
    assert response.reply_markup is not None
    assert [[button.text for button in row] for row in response.reply_markup.inline_keyboard] == [
        ["⬅️ Sebelumnya"],
        ["🔙 Kembali ke Report"],
    ]
    assert [[button.callback_data for button in row] for row in response.reply_markup.inline_keyboard] == [
        [f"{CALLBACK_REPORT_EXPENSE_LOG_PREFIX}1"],
        [CALLBACK_REPORT_BACK_TO_MENU],
    ]


def test_build_transaction_log_response_normalizes_low_page_and_empty_state() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)

    response = build_transaction_log_response("income", connection=connection, user_id=user_id, page=0)

    assert response.text == "Belum ada riwayat pemasukan."
    assert response.reply_markup is not None
    assert [[button.text for button in row] for row in response.reply_markup.inline_keyboard] == [
        ["🔙 Kembali ke Report"]
    ]
    assert [[button.callback_data for button in row] for row in response.reply_markup.inline_keyboard] == [
        [CALLBACK_REPORT_BACK_TO_MENU]
    ]


def test_parse_report_page_returns_page_number_or_one_for_invalid_data() -> None:
    from bot04.bot.handlers_reports import parse_report_page

    assert parse_report_page("report_income_log:2", CALLBACK_REPORT_INCOME_LOG_PREFIX) == 2
    assert parse_report_page("report_income_log:not-a-number", CALLBACK_REPORT_INCOME_LOG_PREFIX) == 1
    assert parse_report_page("other:3", CALLBACK_REPORT_INCOME_LOG_PREFIX) == 1


def test_build_investment_report_response_formats_investment_summary() -> None:
    connection = setup_connection()
    user_id = setup_user(connection)
    add_transaction(
        connection,
        user_id=user_id,
        type="income",
        category_name="Gaji",
        amount=5_000_000,
        transaction_date="2026-05-30",
    )
    add_transaction(
        connection,
        user_id=user_id,
        type="investment",
        category_name="Crypto",
        amount=1_000_000,
        transaction_date="2026-05-30",
    )

    response = build_investment_report_response(
        connection=connection,
        user_id=user_id,
        current_date=date(2026, 5, 30),
    )

    assert response.text == (
        "📈 Laporan Investasi\n"
        "Total Investasi: Rp1.000.000\n"
        "Persentase dari Pemasukan: 20.00%"
    )
