"""Tests for Bot04 report text formatting."""

from __future__ import annotations

from datetime import date

from bot04.reports.formatter import (
    format_category_report,
    format_investment_report,
    format_period_report,
    format_transaction_log_report,
)
from finance_core.db.transactions import Transaction
from finance_core.reports.aggregator import CategoryTotal, ReportSummary
from finance_core.reports.date_ranges import DateRange


def summary() -> ReportSummary:
    return ReportSummary(
        total_income=5_000_000,
        total_expense=100_000,
        total_investment=1_000_000,
        net=3_900_000,
        average_expense=50_000,
        top_expense_categories=[
            CategoryTotal(name="Transportasi", amount=75_000),
            CategoryTotal(name="Makan & Minum", amount=25_000),
        ],
        investment_percentage=20.0,
    )


def test_format_period_report_supports_daily_report() -> None:
    assert format_period_report(
        title="Laporan Harian",
        date_range=DateRange(date(2026, 5, 30), date(2026, 5, 30)),
        summary=summary(),
    ) == (
        "📊 Laporan Harian\n"
        "Periode: 30 Mei 2026\n\n"
        "Pemasukan: Rp5.000.000\n"
        "Pengeluaran: Rp100.000\n"
        "Investasi: Rp1.000.000\n"
        "Sisa Bersih: Rp3.900.000\n"
        "Rata-rata Pengeluaran: Rp50.000\n\n"
        "Top Pengeluaran:\n"
        "1. Transportasi — Rp75.000\n"
        "2. Makan & Minum — Rp25.000"
    )


def test_format_period_report_supports_weekly_or_monthly_date_range() -> None:
    report = format_period_report(
        title="Laporan Mingguan",
        date_range=DateRange(date(2026, 5, 25), date(2026, 5, 31)),
        summary=summary(),
    )

    assert report.startswith("📊 Laporan Mingguan\nPeriode: 25 Mei 2026 - 31 Mei 2026")


def test_format_period_report_shows_empty_category_message() -> None:
    empty_summary = ReportSummary(
        total_income=0,
        total_expense=0,
        total_investment=0,
        net=0,
        average_expense=0,
        top_expense_categories=[],
        investment_percentage=0.0,
    )

    report = format_period_report(
        title="Laporan Bulanan",
        date_range=DateRange(date(2026, 5, 1), date(2026, 5, 31)),
        summary=empty_summary,
    )

    assert "Top Pengeluaran:\n-" in report


def test_format_category_report_supports_income_and_expense_categories() -> None:
    categories = [
        CategoryTotal(name="Gaji", amount=5_000_000),
        CategoryTotal(name="Bonus", amount=100_000),
    ]

    assert format_category_report(title="Kategori Pemasukan", categories=categories) == (
        "🗂 Kategori Pemasukan\n"
        "1. Gaji — Rp5.000.000\n"
        "2. Bonus — Rp100.000"
    )


def test_format_category_report_handles_empty_categories() -> None:
    assert format_category_report(title="Kategori Pengeluaran", categories=[]) == (
        "🗂 Kategori Pengeluaran\n-"
    )


def test_format_investment_report_formats_investment_summary() -> None:
    assert format_investment_report(summary()) == (
        "📈 Laporan Investasi\n"
        "Total Investasi: Rp1.000.000\n"
        "Persentase dari Pemasukan: 20.00%"
    )


def test_format_transaction_log_report_formats_income_history() -> None:
    transactions = [
        Transaction(
            id=1,
            user_id=1,
            type="income",
            category_id=10,
            amount=5_000_000,
            note="gaji bulanan",
            asset_name=None,
            transaction_date="2026-05-31",
        ),
        Transaction(
            id=2,
            user_id=1,
            type="income",
            category_id=11,
            amount=150_000,
            note=None,
            asset_name=None,
            transaction_date="2026-05-30",
        ),
    ]

    report = format_transaction_log_report(
        transaction_type="income",
        transactions=transactions,
        category_names={10: "Gaji"},
        page=1,
        total_pages=3,
    )

    assert report == (
        "💰 Riwayat Pemasukan\n"
        "Halaman 1 dari 3\n"
        "Urutan: terbaru dulu\n\n"
        "1. 31 Mei 2026 — Rp5.000.000\n"
        "   Kategori: Gaji\n"
        "   Catatan: gaji bulanan\n\n"
        "2. 30 Mei 2026 — Rp150.000\n"
        "   Kategori: Lainnya\n"
        "   Catatan: -"
    )


def test_format_transaction_log_report_formats_expense_history_and_empty_state() -> None:
    transaction = Transaction(
        id=1,
        user_id=1,
        type="expense",
        category_id=20,
        amount=25_000,
        note="makan siang",
        asset_name=None,
        transaction_date="2026-05-31",
    )

    report = format_transaction_log_report(
        transaction_type="expense",
        transactions=[transaction],
        category_names={20: "Makan & Minum"},
        page=2,
        total_pages=2,
    )

    assert report == (
        "💸 Riwayat Pengeluaran\n"
        "Halaman 2 dari 2\n"
        "Urutan: terbaru dulu\n\n"
        "1. 31 Mei 2026 — Rp25.000\n"
        "   Kategori: Makan & Minum\n"
        "   Catatan: makan siang"
    )
    assert format_transaction_log_report(
        transaction_type="income",
        transactions=[],
        category_names={},
        page=1,
        total_pages=1,
    ) == "Belum ada riwayat pemasukan."
    assert format_transaction_log_report(
        transaction_type="expense",
        transactions=[],
        category_names={},
        page=1,
        total_pages=1,
    ) == "Belum ada riwayat pengeluaran."
