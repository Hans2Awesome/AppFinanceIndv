"""Tests for Bot04 help text."""

from __future__ import annotations

from bot04.bot.help_text import build_help_text


def test_help_text_prioritizes_quick_input_examples() -> None:
    help_text = build_help_text()

    assert help_text.startswith("Cara tercepat mencatat transaksi adalah langsung ketik pesan.")
    assert "Contoh input cepat:" in help_text
    assert "- makan 25000" in help_text
    assert "- kopi 25k kemarin" in help_text
    assert "- gojek 15000 kantor" in help_text
    assert "- gaji 5000000" in help_text
    assert "- invest btc 100000 dca mingguan" in help_text


def test_help_text_mentions_preview_confirmation_and_reports() -> None:
    help_text = build_help_text()

    assert "preview" in help_text.lower()
    assert "✅ Simpan" in help_text
    assert "/today" in help_text
    assert "/week" in help_text
    assert "/month" in help_text
    assert "/menu" in help_text
    assert "/riwayat_pemasukan" in help_text
    assert "/riwayat_pengeluaran" in help_text
    assert "10 data per halaman" in help_text
    assert "terbaru dulu" in help_text
