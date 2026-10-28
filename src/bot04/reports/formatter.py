"""Format Bot04 report summaries into Telegram-friendly text."""

from __future__ import annotations

from datetime import date

from finance_core.db.transactions import Transaction
from finance_core.reports.aggregator import CategoryTotal, ReportSummary
from finance_core.reports.date_ranges import DateRange

_MONTH_NAMES_ID = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}


def format_period_report(
    *,
    title: str,
    date_range: DateRange,
    summary: ReportSummary,
) -> str:
    """Format daily, weekly, or monthly summary report text."""

    return "\n".join(
        [
            f"📊 {title}",
            f"Periode: {_format_date_range(date_range)}",
            "",
            f"Pemasukan: {_format_rupiah(summary.total_income)}",
            f"Pengeluaran: {_format_rupiah(summary.total_expense)}",
            f"Investasi: {_format_rupiah(summary.total_investment)}",
            f"Sisa Bersih: {_format_rupiah(summary.net)}",
            f"Rata-rata Pengeluaran: {_format_rupiah(summary.average_expense)}",
            "",
            "Top Pengeluaran:",
            _format_category_lines(summary.top_expense_categories),
        ]
    )


def format_category_report(*, title: str, categories: list[CategoryTotal]) -> str:
    """Format income or expense category totals."""

    return "\n".join([f"🗂 {title}", _format_category_lines(categories)])


def format_investment_report(summary: ReportSummary) -> str:
    """Format investment report text."""

    return "\n".join(
        [
            "📈 Laporan Investasi",
            f"Total Investasi: {_format_rupiah(summary.total_investment)}",
            f"Persentase dari Pemasukan: {summary.investment_percentage:.2f}%",
        ]
    )


def format_transaction_log_report(
    *,
    transaction_type: str,
    transactions: list[Transaction],
    category_names: dict[int, str] | None = None,
    page: int,
    total_pages: int,
) -> str:
    """Format paginated income or expense transaction history."""

    if not transactions:
        label = "pemasukan" if transaction_type == "income" else "pengeluaran"
        return f"Belum ada riwayat {label}."

    title = "💰 Riwayat Pemasukan" if transaction_type == "income" else "💸 Riwayat Pengeluaran"
    lines = [
        title,
        f"Halaman {page} dari {total_pages}",
        "Urutan: terbaru dulu",
        "",
    ]
    for index, transaction in enumerate(transactions, start=1):
        category_name = transaction.category_name or (category_names or {}).get(
            transaction.category_id or 0, "Lainnya"
        )
        lines.extend(
            [
                f"{index}. {_format_transaction_date(transaction.transaction_date)} — {_format_rupiah(transaction.amount)}",
                f"   Kategori: {category_name}",
                f"   Catatan: {transaction.note or '-'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def _format_category_lines(categories: list[CategoryTotal]) -> str:
    if not categories:
        return "-"
    return "\n".join(
        f"{index}. {category.name} — {_format_rupiah(category.amount)}"
        for index, category in enumerate(categories, start=1)
    )


def _format_date_range(date_range: DateRange) -> str:
    if date_range.start_date == date_range.end_date:
        return _format_indonesian_date(date_range.start_date)
    return (
        f"{_format_indonesian_date(date_range.start_date)} - "
        f"{_format_indonesian_date(date_range.end_date)}"
    )


def _format_indonesian_date(value: date) -> str:
    return f"{value.day} {_MONTH_NAMES_ID[value.month]} {value.year}"


def _format_transaction_date(value: str) -> str:
    return _format_indonesian_date(date.fromisoformat(value))


def _format_rupiah(amount: int) -> str:
    return f"Rp{amount:,}".replace(",", ".")
