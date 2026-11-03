# Laporan Implementasi: Daftar Perbaikan Akhir Menuju Produksi

Dokumen ini adalah jawaban atas `daftar_perbaikan_akhir_menuju_produksi.md`.
Setiap item checklist diverifikasi langsung di kode, bukan hanya dari hasil
tes. Semua temuan sudah diperbaiki, dites, dan di-push ke `origin/main`.

- Tanggal verifikasi: 2 November 2026
- Basis commit: `ba98bcc` (`origin/main`)
- Status: semua item F1-F6 dan Prioritas 3 selesai

---

## 1. Ringkasan Status

| Item | Judul | Status | Bukti utama |
| :--- | :--- | :--- | :--- |
| F1 | Siklus koneksi bot + health check pool | Selesai | `finance_core/db/connection.py:297,299`; `src/bot04/bot/app.py:710` |
| F2 | Cegah race condition double-submit cicilan | Selesai | `finance_core/db/debts.py:126,372` |
| F3 | Sinkron kas saat edit utang + hapus cicilan | Selesai | `backend/app/routes/debts.py:254,331` |
| F4 | Account linking Mobile ke Telegram | Selesai | `backend/app/routes/auth.py:195`; `src/bot04/bot/app.py:498` |
| F5 | Batas memori rate limiter | Selesai | `backend/app/auth/rate_limit.py:16,52` |
| F6 | Prioritas kategori kustom pada matcher | Selesai | `finance_core/services/category_matcher.py:53` |
| P3.1 | Konfigurasi port Supabase + prepared statement | Selesai | `finance_core/db/connection.py:303`; `.env.example:8` |
| P3.2 | Urutan eksekusi deploy | Selesai | `docs/deploy-supabase.md` |
| P3.3 | Backup berkala | Selesai | `scripts/backup_postgres.sh` |

---

## 2. Detail Per Item

### F1. Siklus koneksi bot dan health check pool

**Yang diminta:** bot tidak menahan satu koneksi statis di `bot_data`, dan
koneksi basi ke Supabase diganti otomatis.

**Yang dikerjakan:**

1. `ConnectionPool` dibuat dengan `max_idle=300` dan
   `check=ConnectionPool.check_connection`
   (`finance_core/db/connection.py:295-303`). Koneksi menganggur lebih dari 5
   menit, atau yang sudah mati di sisi Supabase, dibuang saat diambil lagi.
2. Setiap pesan masuk membuka koneksi sendiri lewat `open_database()` di
   `_with_db_transaction` dan menutupnya di `finally`
   (`src/bot04/bot/app.py:710`). `bot_data` tidak lagi menyimpan koneksi.
3. SQLite memakai `check_same_thread=False` khusus bot, karena handler
   berjalan di thread lain lewat `asyncio.to_thread`.

**Efek:** bot tidak lagi mati dengan error "server closed the connection"
setelah idle semalaman di Supabase.

### F2. Cegah race condition double-submit cicilan

**Yang diminta:** baca baris `debts` dengan `SELECT ... FOR UPDATE` di
PostgreSQL.

**Yang dikerjakan:**

1. `get_debt_by_id(..., for_update=True)` menambahkan klausa `FOR UPDATE` hanya
   saat koneksi PostgreSQL (`finance_core/db/debts.py:126`). SQLite tidak
   mendukung baris lock, jadi flag diabaikan.
2. Dipakai oleh `create_debt_payment` (`debts.py:372`), `delete_debt_payment`
   (`debts.py:278`), dan `update_debt` (`debts.py:167`).

**Catatan penting:** awalnya hanya `create_debt_payment` yang memakai lock. Dua
jalur lain membaca `paid_amount` lalu menulis balik hasil hitungan, jadi dua
request bersamaan bisa menghasilkan saldo yang sama. Ketiganya sekarang memakai
lock yang sama.

### F3. Sinkronisasi kas saat edit utang dan hapus cicilan

**Yang diminta:**

1. `PUT /api/debts/{debt_id}` yang mengubah `total_amount` ikut memperbarui
   baris kas `source_key = debt:<user_id>:<debt_id>`.
2. Endpoint `DELETE /api/debts/{debt_id}/payments/{payment_id}`.

**Yang dikerjakan:**

1. `sync_derived_debt_transaction` dipanggil saat `total_amount` berubah
   (`backend/app/routes/debts.py:254`).
2. Endpoint hapus cicilan ada di `backend/app/routes/debts.py:331`. Ia menghapus
   `debt_payments`, menghapus baris kas `debt_payment:<user>:<payment_id>`,
   mengurangi `paid_amount`, dan mengembalikan status ke `active` bila sisa
   masih ada.
3. `update_debt` sekarang menjaga status tetap konsisten dua arah: `settled`
   dengan `paid_amount < total_amount` kembali ke `active`, dan `active` dengan
   `paid_amount >= total_amount` menjadi `settled`
   (`finance_core/db/debts.py:197`).

**Efek:** nominal utang dan saldo kas tidak bisa lagi berselisih.

### F4. Account linking Mobile ke Telegram

**Yang diminta:** endpoint pembuat kode 6 digit di API dengan TTL 10 menit, dan
perintah `/link <kode>` di bot untuk menggabungkan `telegram_user_id` ke baris
`users` pemilik email Mobile.

**Yang dikerjakan:**

1. Tabel `telegram_link_codes` (migrasi SQLite v4 dan PostgreSQL). Dipakai
   karena API dan bot adalah dua proses terpisah, jadi kode tidak bisa disimpan
   di memori proses API.
2. `POST /api/auth/telegram-link-token` (`backend/app/routes/auth.py:195`):
   - kode 6 digit acak dengan `secrets`;
   - retry sampai 5 kali bila kode bertabrakan, lalu `503`;
   - membuat kode baru menghapus kode lama milik pengguna yang sama, jadi hanya
     kode terbaru yang berlaku.
3. `/link <kode>` di bot (`src/bot04/bot/app.py:498`):
   - `peek_telegram_link_code` memeriksa kode tanpa menghanguskannya
     (`finance_core/db/users.py:237`);
   - `link_telegram_account` menggabungkan akun (`users.py:289`);
   - kode baru dihanguskan setelah penggabungan berhasil.
4. Penggabungan memindahkan transaksi, utang, dan jadwal berulang; memetakan
   kategori bot ke kategori pemilik; lalu menghapus baris bot.
5. `source_key` yang memuat id bot ditulis ulang ke id pemilik
   (`users.py:373`). Tanpa ini, hapus utang setelah linking tidak menemukan
   baris kasnya dan meninggalkan baris yatim.
6. Mobile punya UI-nya di Pengaturan: tombol minta kode, lalu panduan mengirim
   `/link <kode>` ke Bot04 (`mobile/app/(tabs)/settings.tsx`). Status
   `telegram_linked` dikirim di profil (`backend/app/models/schemas.py:51`).

**Pengamanan:** hanya baris bot "murni" (tanpa `email` dan `password_hash`)
yang boleh digabung dan dihapus. Bila Telegram sudah terhubung ke akun Mobile
berkredensial lain, penggabungan ditolak dengan `ValueError`
(`users.py:305`), sehingga kode tautan tidak bisa dipakai mengambil alih akun.
Ini bug nyata yang ditemukan saat audit ulang: sebelum diperbaiki, kode link
bisa memindahkan `telegram_user_id` milik korban ke akun penyerang.

### F5. Batas memori rate limiter

**Yang diminta:** batas kapasitas pada `_buckets` agar RAM tidak habis oleh
serbuan IP acak.

**Yang dikerjakan:** `MAX_BUCKETS = 10_000`
(`backend/app/auth/rate_limit.py:16`) dengan eviction FIFO saat kapasitas penuh
(`rate_limit.py:52`).

**Batas yang diketahui:** limiter masih in-process. Satu worker aman. Bila API
dijalankan multi-worker, tiap worker punya hitungan sendiri dan batas login
jadi lebih longgar. Redis baru diperlukan saat itu.

### F6. Prioritas kategori kustom pada matcher

**Yang diminta:** cek kategori kustom pengguna sebelum kamus default.

**Yang dikerjakan:**

1. `match_category(text, custom_categories=...)` mencocokkan kategori kustom
   lebih dulu (`finance_core/services/category_matcher.py:53`).
2. Pencocokan memakai batas kata (`re.search(rf"\b{re.escape(...)}\b", ...)`),
   bukan substring. Tanpa ini, kategori bernama `Asi` salah menangkap `kasir`
   dan `Bun` menangkap `sabun`.
3. Tersambung di tiga jalur: parser inti
   (`finance_core/services/quick_input_parser.py:51,69`), endpoint API preview
   dan konfirmasi (`backend/app/routes/transactions.py:109,148`), dan handler
   quick input bot (`src/bot04/bot/handlers_quick_input.py:61`).

**Catatan audit:** sebelumnya parameter `custom_categories` hanya ada di parser
dan bot, endpoint API belum mengirimnya. Item checklist jadi tidak berfungsi
untuk pengguna mobile sampai diperbaiki.

### P3.1. Konfigurasi port Supabase

**Yang dikerjakan:**

1. API dan bot memakai transaction pooler port `6543`, didokumentasikan di
   `.env.example:8` dan `README.md`.
2. `prepare_threshold: None` diset pada argumen koneksi
   (`finance_core/db/connection.py:303`), karena transaction pooler tidak
   mendukung prepared statements lintas transaksi.
3. Skrip migrasi memakai direct/session DSN port `5432`, karena DDL dan
   penyalinan data harus satu sesi utuh (`docs/deploy-supabase.md:38-48`,
   `README.md`).

**Koreksi dokumen:** README sebelumnya menyuruh memakai `$DATABASE_URL` (yang
berisi DSN pooler) untuk skrip migrasi. Sudah diganti dengan contoh DSN direct.

### P3.2. Urutan eksekusi deploy

**Yang dikerjakan:** `docs/deploy-supabase.md` berisi urutan lengkap:

1. siapkan DSN pooler dan DSN direct;
2. hentikan layanan lama dan backup `bot04.sqlite3`;
3. isi `.env` VPS;
4. buat skema dan salin data dengan DSN direct;
5. nyalakan API lebih dulu, cek health;
6. nyalakan bot;
7. verifikasi pasca-deploy;
8. pasang backup mingguan;
9. langkah rollback bila gagal.

### P3.3. Backup berkala

**Yang dikerjakan:** `scripts/backup_postgres.sh`:

- `pg_dump --no-owner --format=plain | gzip` ke `BACKUP_DIR`
  (`finance_${date}.sql.gz`);
- retensi `RETENTION_DAYS` (default 30);
- exit non-zero bila `DATABASE_URL` kosong, `pg_dump` tidak ada, atau hasil
  dump kosong, sehingga cron bisa melaporkan kegagalan;
- contoh baris cron ada di header skrip dan di `docs/deploy-supabase.md:77`.

---

## 3. Temuan Tambahan di Luar Checklist

Audit ulang menemukan sembilan bug yang tidak tertulis di checklist. Semua
sudah diperbaiki dan punya tes regresi.

| # | Temuan | Dampak | Perbaikan |
| :--- | :--- | :--- | :--- |
| 1 | Kode link bisa mengambil alih akun Mobile berkredensial | Account hijack | Tolak merge bila baris target punya kredensial (`users.py:305`) |
| 2 | `source_key` tidak di-rebase saat merge | Baris kas yatim setelah hapus utang | `REPLACE(source_key, ':bot:', ':owner:')` (`users.py:373`) |
| 3 | Kode lama tetap valid setelah buat kode baru | Dua kode aktif sekaligus | Hapus kode lama per pengguna (`users.py:220`) |
| 4 | Kode hangus walau linking ditolak | Pengguna harus minta kode baru | `peek_telegram_link_code` sebelum merge (`users.py:229`) |
| 5 | Tabrakan kode acak memicu error 500 | Endpoint gagal total | Retry 5 kali, lalu `503` (`auth.py:206`) |
| 6 | `Asi` cocok di dalam `kasir` | Kategori salah | Pencocokan word-boundary (`category_matcher.py:59`) |
| 7 | Utang `settled` dengan `paid < total` nyangkut | Sisa utang tidak pernah ditagih | Status konsisten dua arah (`debts.py:197`) |
| 8 | `update_debt` dan `delete_debt_payment` tanpa lock | Saldo bisa salah saat request bersamaan | `for_update=True` di kedua jalur |
| 9 | Scheduler berulang bisa jalan ganda antar worker | `next_run_date` maju dua kali | `FOR UPDATE` + cek nilai sebelum proses (`recurring.py:277`) |

Tambahan kecil:

- CI kini menjalankan service PostgreSQL dan menyetel `POSTGRES_TEST_URL`, jadi
  jalur database produksi benar-benar diuji (`.github/workflows/ci.yml:13`).
  Sebelumnya lima tes PostgreSQL selalu di-skip di CI.
- Mobile punya UI tautan Telegram, bukan hanya endpoint backend.
- `telegram_linked` ditambahkan ke respons profil.

---

## 4. Hasil Verifikasi

Dijalankan pada commit `ba98bcc`, kecuali disebut lain.

```text
ruff check .                          All checks passed
pytest tests/ backend/tests           228 passed, 5 skipped
POSTGRES_TEST_URL=... pytest          5 passed
pytest dengan kedua env (simulasi CI) 233 passed
pytest tests/                         179 passed, 5 skipped
pytest backend/tests/                 49 passed
npx tsc --noEmit (mobile)             bersih
```

Migrasi data diuji ke PostgreSQL lokal `finance_migrate`:

```text
PostgreSQL schema version: 4
users: 3, categories: 60, transactions: 23, debts: 4, debt_payments: 5
verify users/categories/transactions/debts/debt_payments: ok
Done. 95 row(s) copied.
```

Dijalankan ulang: hasil identik, tidak ada duplikasi (`ON CONFLICT (id) DO
NOTHING`), sequence tetap benar.

Smoke test API di atas data hasil migrasi memakai token langsung: daftar
transaksi 13 baris untuk `tes@gmail.com`, utang 1 baris berstatus `settled`,
laporan harian `200`, kategori 20 baris, jadwal berulang `200`.

Catatan: `test_postgres_api_round_trip` sempat gagal karena tes memakai
parameter `date`, padahal endpoint memakai `target_date`. Itu bug di tes, bukan
di aplikasi. Sudah diperbaiki.

---

## 5. Commit Terkait

| Commit | Isi |
| :--- | :--- |
| `de3f63f` | Migrasi Supabase/PostgreSQL dan penutupan celah pra-produksi |
| `87d7c0f` | Perbaikan hasil audit: hijack, rebase, kode, matcher, status utang, backup, deploy doc |
| `951e68c` | UI tautan Telegram di mobile + konsumsi kode yang aman |
| `cf19563` | README memakai DSN direct untuk langkah migrasi |
| `f10cc3b` | CI menjalankan tes PostgreSQL dengan service nyata |
| `5e60ec9` | Lock baris utang saat edit dan hapus cicilan |
| `ba98bcc` | Serialisasi scheduler berulang antar worker |

---

## 6. Sisa Pekerjaan (menunggu tindakan pemilik proyek)

1. **Buat project Supabase.** Belum ada, jadi kredensial dan migrasi produksi
   belum dijalankan. Jangan pernah menempelkan DSN atau password ke chat.
2. **Samakan nama unit systemd.** `docs/deploy-supabase.md` memakai
   `finance-api` dan `finance-bot`. Sesuaikan dengan nama unit nyata di VPS.
3. **Pasang `pg_dump` versi >= server.** Klien PostgreSQL lama tidak bisa
   mendump server Supabase yang lebih baru.
4. **Backup masih lokal.** Tambahkan `rclone copy` atau unggah ke object
   storage setelah `pg_dump` agar backup tidak hilang bersama VPS.
5. **Rate limiter satu proses.** Cukup untuk satu worker; pindah ke Redis bila
   API dijalankan multi-worker.
6. **`_DB_LOCK` di bot.** Masih menyerialkan semua query per proses. Aman,
   tetapi bisa dilepas untuk PostgreSQL agar query paralel.
7. **Laporan agregasi di Python.** Cukup untuk data pribadi; pindahkan ke
   `SUM ... GROUP BY` bila volume transaksi membesar.

---

## 7. Catatan Kompatibilitas

- SQLite tetap default untuk pengembangan lokal dan tes. PostgreSQL hanya aktif
  bila `DATABASE_URL` diisi.
- FastAPI tetap satu-satunya lapisan API. Mobile dan bot tidak pernah menyentuh
  database langsung.
- Autentikasi tetap JWT dan bcrypt milik backend; Supabase Auth tidak dipakai.
- Data SQLite lama ikut pindah dengan id asli, termasuk `source_key`.
- Penulisan tetap SQL mentah lewat repositori; lapisan kompatibilitas
  menerjemahkan dialek SQLite.
