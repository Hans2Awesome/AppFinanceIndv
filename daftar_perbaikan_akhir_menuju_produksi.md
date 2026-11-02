Dokumentasi `jawaban_audit_teknis_lanjutan.md` yang kamu lampirkan luar biasa detail dan jujur secara teknis. Banyak *developer* baru menyadari masalah seperti reset `SEQUENCE` PostgreSQL (`pg_get_serial_sequence` + `setval`) atau *single-flight token refresh* (`refreshPromise`) setelah aplikasi meledak di *production*, sementara di repositori ini keduanya sudah tertangani dengan rapi.

Namun, justru karena kamu membuka detail implementasi baris demi baris, terlihat **3 celah kritis tersembunyi** yang luput dari kesimpulan di bagian akhir dokumenmu. Ketiga celah ini hampir pasti akan menimbulkan *bug* fatal begitu aplikasi disambungkan ke Supabase dan dipakai bersamaan dari HP maupun Bot Telegram.

Berikut adalah bedah temuan baru tersebut beserta **Daftar Perbaikan Akhir (*Final Pre-Production Checklist*)** sebelum proyek ini benar-benar siap masuk tahap produksi penuh.

---

## Temuan Kritis Baru dari Hasil Audit Kode

### 1. Kontradiksi "Satu Sumber Kebenaran" antara Mobile & Bot (Poin 6.1)
Di awal perancangan, tujuan utama menaruh semua logika di `finance_core/` adalah agar **"bot dan mobile melihat data yang identik"**. Namun, pada bagian **6.1** terungkap bahwa **tidak ada mekanisme *linking* antara akun Android (`email`) dan akun Telegram (`telegram_user_id`)**.
* **Dampak Nyata:** Saat pengguna mengunduh aplikasi Android dan mendaftar dengan email, mereka mendapat `user_id = 10`. Saat mereka membuka Bot Telegram dan mengetik `/start`, `get_or_create_user` membuat baris baru `user_id = 11`. Keduanya hidup di database yang sama, tetapi **datanya terpisah total**. Pengguna tidak bisa mencatat pengeluaran lewat chat Telegram lalu melihat laporannya di aplikasi Android.
* **Solusi Cepat:** Buat alur *Account Linking* sederhana menggunakan kode OTP/token 6 karakter berbatas waktu (misal 10 menit):
  1. Di aplikasi Mobile, buat tombol **"Hubungkan Telegram"** (`POST /api/auth/telegram-link-token`) yang menghasilkan kode unik (misal: `A7X9K2`).
  2. Pengguna mengirim `/link A7X9K2` di Bot Telegram.
  3. Bot memverifikasi kode tersebut. Jika `telegram_user_id` sudah terlanjur punya baris `user_id` kosong/baru dari `/start`, pindahkan transaksi/utang yang ada ke `user_id` utama milik akun Mobile, hapus baris `user_id` duplikat dari bot, lalu isi kolom `telegram_user_id` pada baris akun Mobile utama.

### 2. Bom Waktu Koneksi Tunggal pada Bot Telegram ke Supabase (Poin 1.2)
Pada bagian **1.2**, tertulis bahwa Bot Telegram membuka **satu koneksi shared (`open_database()`) saat startup** dan menyimpannya di `application.bot_data["connection"]` selamanya untuk semua *handler*.
* **Mengapa Aman di SQLite tapi Fatal di Supabase:** Di SQLite, koneksi hanyalah *file handle* lokal di disk VPS yang tidak pernah kedaluwarsa. Sebaliknya, koneksi ke Supabase melewati internet dan *connection pooler* (Supavisor) / *firewall* cloud yang **otomatis memutus koneksi TCP yang menganggur (*idle*) setelah beberapa menit**.
* **Dampak Nyata:** Jika tidak ada yang mengirim chat ke Bot Telegram selama 30 menit, Supabase akan menutup koneksi TCP tersebut secara sepihak. Saat pengguna mengirim chat lagi, `application.bot_data["connection"]` sudah menjadi *dead connection*. Eksekusi query di dalam `_with_db_transaction` akan melempar `psycopg.OperationalError: consuming input failed / SSL SYSCALL error: EOF detected` dan gagal memproses pesan.
* **Solusi:** Jangan simpan satu objek koneksi tunggal selamanya di `bot_data`. Gunakan pola yang **sama persis dengan FastAPI (`get_db()`)**: pada dekorator/pembungkus `_with_db_transaction`, panggil `open_database()` (yang otomatis mengambil koneksi sehat dari `ConnectionPool` `psycopg_pool`) di awal *handler*, lalu panggil `close()` (mengembalikan ke *pool*) di blok `finally`. Selain itu, pastikan `ConnectionPool` di `finance_core/db/connection.py:276-299` menambahkan parameter `check=ConnectionPool.check_connection` agar *pool* selalu memvalidasi koneksi sebelum diberikan ke *handler*.

### 3. Inkonsistensi Kas saat Nominal Utang Diedit via `PUT /api/debts/{debt_id}` (Poin 2.1 & 3.4)
Pada bagian **2.1**, dijelaskan bahwa pengguna bisa mengubah `total_amount` utang lewat `PUT /api/debts/{debt_id}`. Sementara di bagian **3.4**, saat utang pertama kali dibuat dengan `sync_cash=True`, sistem otomatis membuat baris transaksi kas dengan `source_key = debt:<user_id>:<debt_id>`.
* **Dampak Nyata:** Pengguna membuat utang Rp 500.000 (`sync_cash=True`) $\rightarrow$ tercipta transaksi kas masuk Rp 500.000. Lima menit kemudian pengguna sadar salah ketik (seharusnya Rp 50.000) lalu mengeditnya lewat `PUT /api/debts/{debt_id}`. Fungsi `update_debt` di `finance_core/db/debts.py:158-192` memperbarui `debts.total_amount` menjadi Rp 50.000, **tetapi transaksi kas `debt:<user_id>:<debt_id>` di tabel `transactions` tetap bernilai Rp 500.000** (dan tidak bisa diedit manual oleh user karena sudah dikunci oleh guard P1). Saldo kas pengguna akan selisih Rp 450.000 selamanya.
* **Solusi:** Di dalam `PUT /api/debts/{debt_id}`, jika `total_amount` berubah dan terdapat baris transaksi dengan `source_key = f"debt:{user_id}:{debt_id}"`, perbarui juga kolom `amount` pada baris transaksi tersebut di dalam blok `with transaction(db)` yang sama (buat fungsi internal `sync_derived_transaction_amount` yang diizinkan melewati guard P1).

---

## Daftar Perbaikan Akhir (*Final Pre-Production Checklist*)

Berikut adalah urutan kerja yang paling efisien untuk menutup seluruh celah di atas sebelum kamu menyalakan Supabase dan merilis aplikasi:

### Prioritas 1: Kestabilan Koneksi & Integritas Data (Wajib Sebelum Supabase Aktif)

| ID | Tugas Perbaikan | File Target | Detail Implementasi Teknis |
| :--- | :--- | :--- | :--- |
| **F1** | **Perbaiki Siklus Koneksi Bot Telegram & Health Check Pool** | `src/bot04/bot/app.py` & `finance_core/db/connection.py` | 1. Ubah `_with_db_transaction` di bot agar memanggil `open_database()` per pesan masuk dan `close()` di `finally` (menggunakan *pool*, bukan menahan 1 koneksi statis di `bot_data`).<br>2. Tambahkan `check=ConnectionPool.check_connection` dan `max_idle=300` pada inisialisasi `ConnectionPool` (`connection.py:276`) agar koneksi basi ke Supabase otomatis diganti. |
| **F2** | **Cegah *Race Condition* Double-Submit Cicilan** | `finance_core/db/debts.py` | Pada `create_debt_payment` (`debts.py:274`): saat membaca baris `debts` untuk mengecek `remaining = total_amount - paid_amount`, gunakan query `SELECT ... FOR UPDATE` ketika berjalan di PostgreSQL (lapisan kompatibilitas di `connection.py` bisa menghapus klausa `FOR UPDATE` jika driver-nya SQLite). |
| **F3** | **Sinkronisasi Kas saat Edit Nominal Utang & Hapus Cicilan** | `backend/app/routes/debts.py` & `finance_core/db/debts.py` | 1. Saat `PUT /api/debts/{debt_id}` mengubah `total_amount`, ikut perbarui `amount` pada `transactions` yang memiliki `source_key = f"debt:{user_id}:{debt_id}"`.<br>2. Tambahkan endpoint `DELETE /api/debts/{debt_id}/payments/{payment_id}` yang menghapus baris `debt_payments`, menghapus transaksi `debt_payment:{user_id}:{payment_id}`, mengurangi `debts.paid_amount`, dan mengembalikan status `settled` ke `unpaid/active` jika `paid_amount < total_amount`. |

---

### Prioritas 2: Penyatuan Pengalaman Pengguna & Keamanan Memori (Wajib Sebelum Rilis Publik)

| ID | Tugas Perbaikan | File Target | Detail Implementasi Teknis |
| :--- | :--- | :--- | :--- |
| **F4** | **Mekanisme *Account Linking* Mobile $\leftrightarrow$ Telegram** | `backend/app/routes/auth.py` & `src/bot04/bot/` | Tambahkan endpoint pembuat kode tautan 6 digit di API (simpan di tabel/memori dengan TTL 10 menit) dan perintah `/link <kode>` di Bot Telegram untuk menggabungkan `telegram_user_id` ke baris `users` pemilik `email` Mobile. |
| **F5** | **Batas Memori (*Max Keys Eviction*) pada Rate Limiter** | `backend/app/auth/rate_limit.py` | Karena aplikasi di VPS pribadi kemungkinan besar berjalan 1 *worker* (sehingga belum mendesak pakai Redis), cukup tambahkan batas kapasitas pada `_buckets: dict[str, _Bucket]` (misal `MAX_BUCKETS = 10_000`). Jika ukuran `len(_buckets) >= MAX_BUCKETS`, jalankan sapu bersih `_prune_all()` atau buang kunci tertua (`pop(next(iter(_buckets)))`) agar RAM VPS tidak pernah habis diserang ribuan IP acak. |
| **F6** | **Prioritas Kategori Kustom pada `category_matcher.py`** | `finance_core/services/category_matcher.py` | Pada poin 3.3 disebutkan matcher hanya mencocokkan `DEFAULT_CATEGORIES` statis. Tambahkan langkah pengecekan sederhana: sebelum mencocokkan ke kamus default, cek apakah ada kata di input cepat yang sama persis (*case-insensitive substring match*) dengan nama kategori kustom milik user di database. |

---

### Prioritas 3: Kesiapan Operasional & *Deployment* (Saat Pindah ke Supabase)

1. **Konfigurasi Port Supabase (`DATABASE_URL`):**
   * Untuk penggunaan harian API + Bot (`settings.database_url`), gunakan **Transaction Pooler (port 6543)** atau **Session Pooler (port 5432 pada host pooler Supabase)**. Jika menggunakan `psycopg` v3 dengan port `6543` (Supavisor mode transaksi), pastikan `prepare_threshold=None` disetel pada argumen koneksi `psycopg` di `connection.py` karena *transaction pooler* tidak mendukung *prepared statements* lintas transaksi.
   * Untuk menjalankan `scripts/migrate_sqlite_to_postgres.py`, gunakan **Direct Connection / Session Mode (port 5432)** agar proses DDL (`run_migrations`) dan penyalinan data berjalan dalam satu sesi utuh.
2. **Urutan Eksekusi Deploy:**
   * Matikan sementara layanan API dan Bot yang masih mengarah ke `bot04.sqlite3`.
   * Isi `DATABASE_URL` di `.env` VPS.
   * Jalankan `python scripts/migrate_sqlite_to_postgres.py` dan pastikan verifikasi jumlah baris serta `_reset_sequence` sukses 100%.
   * Nyalakan layanan FastAPI terlebih dahulu, disusul layanan Bot Telegram.
3. **Backup Berkala:**
   * Karena Supabase Free Plan tidak menyediakan *automated point-in-time backup* yang bisa diunduh otomatis tanpa batas, pasang *cronjob* mingguan sederhana di VPS (`pg_dump "$DATABASE_URL" | gzip > backup_$(date +%F).sql.gz`) yang disimpan di disk VPS atau diunggah ke Google Drive menggunakan `rclone`.

