"""Tests for Telegram bot command menu configuration."""

from __future__ import annotations

from bot04.bot.app import BOT_COMMANDS


def test_bot_commands_match_bot03_style_menu_for_bot04() -> None:
    assert [(command.command, command.description) for command in BOT_COMMANDS] == [
        ("start", "🚀 Jalankan Bot"),
        ("menu", "📋 Menu Utama"),
        ("help", "💡 Bantuan Input Cepat"),
        ("today", "📅 Laporan Hari Ini"),
        ("week", "🗓 Laporan Minggu Ini"),
        ("month", "📆 Laporan Bulan Ini"),
        ("report", "📊 Menu Laporan"),
        ("riwayat_pemasukan", "💰 Riwayat Pemasukan"),
        ("riwayat_pengeluaran", "💸 Riwayat Pengeluaran"),
    ]
