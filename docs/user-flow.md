# Bot04 — Telegram Personal Finance Tracker

Bot04 adalah chatbot Telegram untuk mencatat pemasukan, pengeluaran, investasi, dan menampilkan laporan keuangan personal per user Telegram.

## Tujuan Utama

Setiap user Telegram memiliki data keuangan sendiri, terpisah berdasarkan `telegram_user_id`. Bot membantu user mencatat transaksi harian dengan cepat, lalu menyajikan laporan berdasarkan periode, kategori, dan tipe transaksi.

## Entitas Utama

- **User**: pemilik data keuangan, diidentifikasi dari Telegram user ID.
- **Transaction**: catatan pemasukan, pengeluaran, atau investasi.
- **Category**: kategori pemasukan/pengeluaran/investasi.
- **Wallet/Account**: sumber dana opsional, misalnya cash, bank, e-wallet.
- **Report**: ringkasan harian, mingguan, bulanan, kategori, dan investasi.

## Tipe Transaksi

1. **Pemasukan**
   - Contoh: gaji, bonus, hadiah, freelance, jualan.
2. **Pengeluaran**
   - Contoh: makan, transport, belanja, tagihan, hiburan.
3. **Investasi**
   - Contoh: saham, crypto, reksadana, emas, deposito.

## Gambaran Flow User

### 1. Start / Onboarding

User membuka bot dan menekan `/start`.

Bot menampilkan pesan sambutan:

- Penjelasan singkat fungsi bot.
- Data setiap user bersifat terpisah berdasarkan akun Telegram.
- Tombol utama:
  - `➕ Catat Transaksi`
  - `📊 Lihat Laporan`
  - `📁 Kategori`
  - `💼 Wallet`
  - `⚙️ Pengaturan`

Flow awal:

1. User tekan `/start`.
2. Bot cek apakah user sudah pernah terdaftar.
3. Jika belum, bot membuat profil user otomatis dari Telegram ID.
4. Bot menampilkan menu utama.

### 2. Menu Utama

Menu utama sebaiknya menggunakan inline keyboard agar user tidak perlu mengetik command panjang.

Tampilan menu:

- `➕ Pemasukan`
- `➖ Pengeluaran`
- `📈 Investasi`
- `📊 Laporan`
- `🗂 Kategori`
- `⚙️ Pengaturan`

Bot juga bisa mendukung input cepat lewat teks, misalnya:

- `makan 25000`
- `gaji 5000000`
- `invest btc 100000`
- `transport 15000 gojek`

### 3. Flow Catat Pemasukan

User memilih `➕ Pemasukan`.

Bot bertanya bertahap:

1. Pilih kategori pemasukan:
   - Gaji
   - Bonus
   - Freelance
   - Bisnis
   - Hadiah
   - Lainnya
2. Masukkan nominal.
3. Tambahkan catatan opsional.
4. Pilih tanggal:
   - Hari ini
   - Kemarin
   - Pilih tanggal manual
5. Konfirmasi data.

Contoh konfirmasi:

```text
Catatan Pemasukan
Kategori: Gaji
Nominal: Rp5.000.000
Tanggal: 30 Mei 2026
Catatan: Gaji bulanan

Simpan transaksi ini?
```

Tombol:

- `✅ Simpan`
- `✏️ Edit`
- `❌ Batal`

Setelah disimpan, bot menampilkan saldo/ringkasan singkat:

```text
✅ Pemasukan berhasil dicatat.
Hari ini:
Pemasukan: Rp5.000.000
Pengeluaran: Rp0
Investasi: Rp0
Sisa bersih: Rp5.000.000
```

### 4. Flow Catat Pengeluaran

User memilih `➖ Pengeluaran`.

Bot bertanya:

1. Pilih kategori pengeluaran:
   - Makan & Minum
   - Transportasi
   - Belanja
   - Tagihan
   - Hiburan
   - Kesehatan
   - Pendidikan
   - Lainnya
2. Masukkan nominal.
3. Tambahkan catatan opsional.
4. Pilih wallet/sumber dana jika fitur wallet aktif.
5. Pilih tanggal.
6. Konfirmasi.

Contoh:

```text
Catatan Pengeluaran
Kategori: Makan & Minum
Nominal: Rp25.000
Wallet: Cash
Tanggal: 30 Mei 2026
Catatan: Sarapan

Simpan transaksi ini?
```

Tombol:

- `✅ Simpan`
- `✏️ Edit`
- `❌ Batal`

### 5. Flow Catat Investasi

User memilih `📈 Investasi`.

Bot bertanya:

1. Pilih jenis investasi:
   - Saham
   - Crypto
   - Reksadana
   - Emas
   - Deposito
   - P2P Lending
   - Lainnya
2. Masukkan nominal investasi.
3. Masukkan nama aset opsional:
   - Contoh: BBCA, BTC, ETH, Antam, SBN.
4. Pilih tanggal.
5. Tambahkan catatan opsional.
6. Konfirmasi.

Contoh:

```text
Catatan Investasi
Jenis: Crypto
Aset: BTC
Nominal: Rp500.000
Tanggal: 30 Mei 2026
Catatan: DCA mingguan

Simpan investasi ini?
```

Laporan investasi dipisahkan dari pengeluaran biasa agar user bisa melihat total uang yang dialokasikan ke aset.

### 6. Input Cepat Lewat Teks

Selain tombol, bot bisa membaca pesan teks sederhana.

Contoh input:

```text
makan 25000
transport 15000 gojek
gaji 5000000
invest btc 100000
```

Flow parsing:

1. Bot membaca kata pertama sebagai kandidat kategori/tipe.
2. Bot membaca angka sebagai nominal.
3. Sisa teks menjadi catatan.
4. Bot menebak tipe transaksi:
   - `gaji`, `bonus`, `freelance` → pemasukan.
   - `makan`, `transport`, `belanja` → pengeluaran.
   - `invest`, `btc`, `saham`, `emas` → investasi.
5. Bot menampilkan preview dan meminta konfirmasi.

Contoh:

```text
Saya mendeteksi transaksi:
Tipe: Pengeluaran
Kategori: Makan & Minum
Nominal: Rp25.000
Catatan: -
Tanggal: Hari ini

Benar?
```

Tombol:

- `✅ Simpan`
- `✏️ Edit`
- `❌ Batal`

### 7. Flow Laporan

User memilih `📊 Laporan`.

Bot menampilkan pilihan laporan:

- `📅 Hari Ini`
- `🗓 Minggu Ini`
- `📆 Bulan Ini`
- `📂 Per Kategori`
- `📈 Investasi`
- `🔎 Custom Tanggal`

### 8. Laporan Harian

Isi laporan harian:

```text
📅 Laporan Hari Ini — 30 Mei 2026

Pemasukan: Rp5.000.000
Pengeluaran: Rp125.000
Investasi: Rp500.000

Sisa Bersih: Rp4.375.000

Top Pengeluaran:
1. Makan & Minum — Rp75.000
2. Transportasi — Rp30.000
3. Hiburan — Rp20.000
```

Tombol lanjutan:

- `📋 Detail Transaksi`
- `📂 Per Kategori`
- `⬅️ Kembali`

### 9. Laporan Mingguan

Isi laporan mingguan:

```text
🗓 Laporan Minggu Ini
Periode: 25–30 Mei 2026

Total Pemasukan: Rp5.000.000
Total Pengeluaran: Rp850.000
Total Investasi: Rp750.000

Sisa Bersih: Rp3.400.000
Rata-rata Pengeluaran/Hari: Rp141.667
```

Tambahan yang berguna:

- Hari dengan pengeluaran terbesar.
- Kategori pengeluaran terbesar.
- Persentase investasi dari pemasukan.

### 10. Laporan Bulanan

Isi laporan bulanan:

```text
📆 Laporan Mei 2026

Pemasukan: Rp7.000.000
Pengeluaran: Rp3.200.000
Investasi: Rp1.000.000

Sisa Bersih: Rp2.800.000
Rasio Tabungan/Investasi: 14,3%
```

Tombol:

- `📂 Detail Kategori`
- `📈 Detail Investasi`
- `📋 Daftar Transaksi`
- `⬅️ Kembali`

### 11. Laporan Per Kategori Pemasukan

User memilih laporan kategori lalu memilih `Pemasukan`.

Contoh:

```text
📂 Pemasukan per Kategori — Mei 2026

1. Gaji — Rp5.000.000 — 71,4%
2. Freelance — Rp1.500.000 — 21,4%
3. Bonus — Rp500.000 — 7,2%

Total Pemasukan: Rp7.000.000
```

### 12. Laporan Per Kategori Pengeluaran

Contoh:

```text
📂 Pengeluaran per Kategori — Mei 2026

1. Makan & Minum — Rp1.200.000 — 37,5%
2. Transportasi — Rp600.000 — 18,8%
3. Tagihan — Rp500.000 — 15,6%
4. Belanja — Rp450.000 — 14,1%
5. Hiburan — Rp300.000 — 9,4%
6. Lainnya — Rp150.000 — 4,6%

Total Pengeluaran: Rp3.200.000
```

### 13. Laporan Investasi

Contoh laporan investasi:

```text
📈 Laporan Investasi — Mei 2026

Total Investasi: Rp1.000.000

Per Jenis:
1. Crypto — Rp500.000
2. Saham — Rp300.000
3. Emas — Rp200.000

Per Aset:
1. BTC — Rp500.000
2. BBCA — Rp300.000
3. Antam — Rp200.000

Persentase dari Pemasukan: 14,3%
```

Catatan: tahap awal cukup mencatat nominal uang yang diinvestasikan, bukan menghitung profit/loss real-time. Fitur valuasi aset bisa masuk fase berikutnya.

### 14. Flow Kategori

User memilih `🗂 Kategori`.

Pilihan:

- `➕ Tambah Kategori`
- `✏️ Edit Kategori`
- `🗑 Hapus Kategori`
- `📋 Lihat Kategori`

Kategori harus terikat ke user agar tiap user bisa punya kategori custom sendiri.

Kategori bawaan dibuat otomatis saat user pertama kali `/start`.

Default kategori pemasukan:

- Gaji
- Bonus
- Freelance
- Bisnis
- Hadiah
- Lainnya

Default kategori pengeluaran:

- Makan & Minum
- Transportasi
- Belanja
- Tagihan
- Hiburan
- Kesehatan
- Pendidikan
- Lainnya

Default kategori investasi:

- Saham
- Crypto
- Reksadana
- Emas
- Deposito
- Lainnya

### 15. Flow Edit / Hapus Transaksi

Dari laporan detail transaksi, user bisa memilih satu transaksi.

Aksi:

- `✏️ Edit Nominal`
- `✏️ Edit Kategori`
- `✏️ Edit Tanggal`
- `✏️ Edit Catatan`
- `🗑 Hapus Transaksi`

Hapus transaksi wajib konfirmasi:

```text
Yakin hapus transaksi ini?
Pengeluaran Makan & Minum Rp25.000 pada 30 Mei 2026
```

Tombol:

- `✅ Ya, Hapus`
- `❌ Batal`

### 16. Flow Wallet Opsional

Wallet berguna jika user ingin memisahkan sumber dana.

Contoh wallet:

- Cash
- BCA
- Mandiri
- GoPay
- OVO
- Dana

Flow wallet:

1. User pilih `💼 Wallet`.
2. Bot menampilkan daftar wallet.
3. User bisa tambah/edit/hapus wallet.
4. Saat mencatat transaksi, user bisa memilih wallet.

Untuk MVP, wallet bisa dibuat opsional agar pencatatan tetap cepat.

### 17. Pengaturan

Menu pengaturan:

- Mata uang default: IDR.
- Zona waktu: Asia/Jakarta.
- Format laporan: ringkas/detail.
- Reminder harian untuk mencatat keuangan.
- Reset data akun.

Reset data harus memakai konfirmasi berlapis.

### 18. Reminder Harian Opsional

Bot bisa mengirim reminder:

```text
⏰ Jangan lupa catat pemasukan/pengeluaran hari ini.
```

User bisa mengatur jam reminder, misalnya 21:00 WIB.

### 19. Command yang Disarankan

- `/start` — mulai bot dan tampilkan menu utama.
- `/menu` — tampilkan menu utama.
- `/income` — catat pemasukan.
- `/expense` — catat pengeluaran.
- `/invest` — catat investasi.
- `/report` — buka menu laporan.
- `/today` — laporan hari ini.
- `/week` — laporan minggu ini.
- `/month` — laporan bulan ini.
- `/categories` — kelola kategori.
- `/help` — bantuan penggunaan.

### 20. Prinsip UX

- Utamakan tombol inline keyboard untuk user awam.
- Semua input penting diberi preview sebelum disimpan.
- Setelah user memilih tombol, edit pesan yang sama jika memungkinkan agar chat tidak penuh.
- Input cepat tetap tersedia untuk power user.
- Laporan harus ringkas di awal, detail dibuka lewat tombol.
- Data user selalu dipisahkan berdasarkan Telegram user ID.

## MVP yang Disarankan

Fase pertama cukup membangun:

1. `/start` dan menu utama.
2. Catat pemasukan.
3. Catat pengeluaran.
4. Catat investasi.
5. Default kategori per user.
6. Laporan harian, mingguan, bulanan.
7. Laporan per kategori pemasukan/pengeluaran.
8. Laporan total investasi.
9. Edit/hapus transaksi dasar.

Fitur setelah MVP:

- Wallet multi-akun.
- Reminder harian.
- Export CSV/Excel.
- Budget per kategori.
- Grafik gambar laporan.
- Valuasi aset investasi real-time.

## Struktur Project Awal yang Disarankan

```text
projects/bot04/
├── README.md
├── docs/
│   └── user-flow.md
├── src/
│   ├── bot/
│   ├── database/
│   ├── reports/
│   └── services/
└── tests/
```
