"""Format transaction preview text for quick input confirmations."""

from __future__ import annotations

from datetime import date
from typing import TypeVar

from finance_core.domain import transaction_type_label
from finance_core.services.quick_input_parser import QuickInputResult

T = TypeVar("T")

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

_REVIEW_WARNING = "Saya belum terlalu yakin dengan kategorinya. Silakan cek sebelum simpan."


def format_transaction_preview(result: QuickInputResult) -> str:
    """Format a parsed transaction preview for user confirmation."""

    if result.error:
        return result.error

    lines = [
        "Saya mendeteksi transaksi:",
        f"Tipe: {transaction_type_label(_require_value(result.type))}",
        f"Kategori: {_require_value(result.category_name)}",
    ]

    if result.asset_name:
        lines.append(f"Aset: {result.asset_name}")

    lines.extend(
        [
            f"Nominal: {_format_rupiah(_require_value(result.amount))}",
            f"Catatan: {result.note or '-'}",
            f"Tanggal: {_format_indonesian_date(_require_value(result.transaction_date))}",
        ]
    )

    if result.needs_review:
        lines.extend(["", _REVIEW_WARNING])

    lines.extend(["", "Benar?"])
    return "\n".join(lines)


def _format_rupiah(amount: int) -> str:
    return f"Rp{amount:,}".replace(",", ".")


def _format_indonesian_date(value: date) -> str:
    return f"{value.day} {_MONTH_NAMES_ID[value.month]} {value.year}"


def _require_value(value: T | None) -> T:
    if value is None:
        raise ValueError("Preview result is missing required data")
    return value
