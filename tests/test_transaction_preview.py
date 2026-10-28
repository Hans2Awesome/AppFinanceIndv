"""Tests for quick transaction preview formatting."""

from __future__ import annotations

from datetime import date

from bot04.services.transaction_preview import format_transaction_preview
from finance_core.services.quick_input_parser import QuickInputResult


def test_format_transaction_preview_renders_readable_preview() -> None:
    result = QuickInputResult(
        type="expense",
        category_name="Makan & Minum",
        amount=25000,
        note="",
        asset_name=None,
        transaction_date=date(2026, 5, 30),
        confidence=1.0,
        needs_review=False,
        original_text="makan 25000",
        error=None,
    )

    assert format_transaction_preview(result) == (
        "Saya mendeteksi transaksi:\n"
        "Tipe: Pengeluaran\n"
        "Kategori: Makan & Minum\n"
        "Nominal: Rp25.000\n"
        "Catatan: -\n"
        "Tanggal: 30 Mei 2026\n\n"
        "Benar?"
    )


def test_format_transaction_preview_includes_note_and_asset_when_present() -> None:
    result = QuickInputResult(
        type="investment",
        category_name="Crypto",
        amount=100000,
        note="dca mingguan",
        asset_name="BTC",
        transaction_date=date(2026, 5, 30),
        confidence=1.0,
        needs_review=False,
        original_text="btc 100000 dca mingguan",
        error=None,
    )

    assert format_transaction_preview(result) == (
        "Saya mendeteksi transaksi:\n"
        "Tipe: Investasi\n"
        "Kategori: Crypto\n"
        "Aset: BTC\n"
        "Nominal: Rp100.000\n"
        "Catatan: dca mingguan\n"
        "Tanggal: 30 Mei 2026\n\n"
        "Benar?"
    )


def test_format_transaction_preview_adds_warning_when_needs_review() -> None:
    result = QuickInputResult(
        type="expense",
        category_name="Lainnya",
        amount=12345,
        note="random",
        asset_name=None,
        transaction_date=date(2026, 5, 30),
        confidence=0.0,
        needs_review=True,
        original_text="random 12345",
        error=None,
    )

    preview = format_transaction_preview(result)

    assert "Saya belum terlalu yakin dengan kategorinya. Silakan cek sebelum simpan." in preview
    assert preview.endswith("Benar?")


def test_format_transaction_preview_returns_error_message_for_parser_error() -> None:
    result = QuickInputResult(
        type=None,
        category_name=None,
        amount=None,
        note="",
        asset_name=None,
        transaction_date=None,
        confidence=0.0,
        needs_review=True,
        original_text="",
        error="Tulis transaksi dulu",
    )

    assert format_transaction_preview(result) == "Tulis transaksi dulu"
