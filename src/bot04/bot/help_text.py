"""Help text for Bot04 Telegram bot."""

from __future__ import annotations


def build_help_text() -> str:
    """Return Telegram-friendly help text focused on quick input."""

    return "\n".join(
        [
            "Cara tercepat mencatat transaksi adalah langsung ketik pesan.",
            "",
            "Contoh input cepat:",
            "- makan 25000",
            "- kopi 25k kemarin",
            "- gojek 15000 kantor",
            "- gaji 5000000",
            "- invest btc 100000 dca mingguan",
            "",
            "Setelah itu bot akan menampilkan preview. Tekan ✅ Simpan kalau sudah benar.",
            "",
            "Command berguna:",
            "- /menu untuk membuka menu utama",
            "- /today untuk laporan hari ini",
            "- /week untuk laporan minggu ini",
            "- /month untuk laporan bulan ini",
            "- /riwayat_pemasukan untuk melihat riwayat pemasukan, 10 data per halaman, terbaru dulu",
            "- /riwayat_pengeluaran untuk melihat riwayat pengeluaran, 10 data per halaman, terbaru dulu",
        ]
    )
