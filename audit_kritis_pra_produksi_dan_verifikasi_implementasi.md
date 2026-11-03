Eksekusi pada laporan implementasi ini (`commit ba98bcc`) sudah berada di level *production-grade*. Kemampuan Anda menemukan dan menutup 9 *bug* tambahan di luar *checklist*—terutama celah *account hijack* pada kode tautan Telegram, penggunaan *word-boundary regex* (`\b...\b`) agar kategori `"Asi"` tidak salah menangkap kata `"kasir"`, hingga mengaktifkan layanan PostgreSQL asli di GitHub Actions CI—menunjukkan kualitas audit yang sangat matang.

Namun, setelah membedah detail laporan dan bukti log yang Anda lampirkan di atas, saya menemukan **4 celah teknis spesifik (termasuk 2 potensi bug tersembunyi)** serta beberapa pertanyaan operasional yang perlu Anda pastikan sebelum benar-benar menekan tombol migrasi di VPS produksi.

---

### 1. Bug Tersembunyi pada `REPLACE(source_key, ':bot:', ':owner:')` (Bagian 3 Temuan #2)

Di laporan disebutkan bahwa saat proses *merge* akun Telegram ke Mobile (`users.py:352`), penulisan ulang `source_key` dilakukan menggunakan fungsi `REPLACE(source_key, ':bot:', ':owner:')`.

* **Masalah Kritis:**
  Perhatikan format `source_key` untuk jadwal transaksi berulang (dari audit sebelumnya):
  `recurring:<user_id>:<schedule_id>:<YYYY-MM-DD>`
  Baik `<user_id>` maupun `<schedule_id>` **sama-sama diapit oleh tanda titik dua (`:`)**.
  Jika kebetulan ID akun bot (`bot_user_id`) memiliki angka yang **sama** dengan `<schedule_id>` (misalnya `bot_user_id = 2`, `schedule_id = 2`, dan `owner_user_id = 1`), maka nilai `source_key` awalnya adalah:
  `recurring:2:2:2026-11-02`
  Fungsi `REPLACE()` di SQL bersifat *global replace* (mengganti semua kemunculan substring di dalam teks). Akibatnya, `REPLACE('recurring:2:2:2026-11-02', ':2:', ':1:')` akan mengubah string tersebut menjadi:
  `recurring:1:1:2026-11-02` (**ID jadwal `schedule_id` ikut berubah dari `2` menjadi `1`!**).
* **Pertanyaan & Solusi:**
  Apakah di `users.py:352` pemanggilan `REPLACE` sudah menyertakan prefix jenis transaksinya?
  Agar tidak pernah salah mengganti `<schedule_id>` di tengah string, pastikan penggantian string selalu dikunci dari prefix awalnya:
  * Ganti `'debt:' || :bot_id || ':'` menjadi `'debt:' || :owner_id || ':'`
  * Ganti `'debt_payment:' || :bot_id || ':'` menjadi `'debt_payment:' || :owner_id || ':'`
  * Ganti `'recurring:' || :bot_id || ':'` menjadi `'recurring:' || :owner_id || ':'`

---

### 2. Apakah Tabel `recurring_transactions` Ikut Disalin pada Skrip Migrasi? (Bagian 4)

Perhatikan output log uji coba migrasi data yang Anda cantumkan di Bagian 4:
```text
PostgreSQL schema version: 4
users: 3, categories: 60, transactions: 23, debts: 4, debt_payments: 5
verify users/categories/transactions/debts/debt_payments: ok
Done. 95 row(s) copied.
```
* **Masalah & Pertanyaan:**
  Pada baris `verify users/categories/transactions/debts/debt_payments: ok`, tabel **`recurring_transactions` sama sekali tidak muncul** di daftar tabel yang disalin maupun diverifikasi oleh `scripts/migrate_sqlite_to_postgres.py`.
  * Apakah tabel `recurring_transactions` memang belum dimasukkan ke dalam daftar tabel di `migrate_sqlite_to_postgres.py`?
  * Jika belum, maka seluruh jadwal transaksi berulang milik pengguna di `bot04.sqlite3` akan **hilang (tidak ikut pindah ke Supabase)** saat migrasi dijalankan, dan perlu segera ditambahkan ke daftar tabel beserta `_reset_sequence`-nya.

---

### 3. Dua Jebakan pada Skrip Backup `scripts/backup_postgres.sh` (Bagian 2 P3.3)

Pada P3.3 disebutkan bahwa `scripts/backup_postgres.sh` menjalankan `pg_dump --no-owner --format=plain | gzip` dan akan *exit non-zero* bila `DATABASE_URL` kosong, `pg_dump` tidak ada, atau hasil dump kosong.

Ada **dua jebakan klasik** di lingkungan Linux untuk skrip seperti ini:
1. **File `.gz` Kosong Tidak Berukuran 0 Byte:**
   Ketika `pg_dump` gagal (misal karena password salah atau koneksi terputus) dan output-nya di-*pipe* ke `gzip > finance_2026-11-03.sql.gz`, program `gzip` tetap menghasilkan *header* dan *footer* kompresi yang valid berukuran sekitar **20 byte**.
   * **Pertanyaan:** Jika skrip Anda mengecek "hasil dump kosong" hanya dengan `[ ! -s "$BACKUP_FILE" ]` (cek ukuran file > 0 byte), pengecekan itu **akan selalu lolos** meskipun isinya kosong melompong! Pastikan di baris atas `backup_postgres.sh` sudah dipasang `set -euo pipefail` agar kegagalan `pg_dump` di sisi kiri *pipe* (`|`) langsung menggagalkan skrip, dan hapus file `.sql.gz` yang gagal terbentuk.
2. **Penggunaan Port `6543` vs `5432` untuk `pg_dump`:**
   Di `.env` produksi nanti, `DATABASE_URL` akan diisi dengan **Transaction Pooler (port 6543)** untuk kebutuhan API dan Bot. Namun, menjalankan `pg_dump` melewati Supavisor Transaction Pooler (port `6543`) berisiko gagal saat mengambil *consistent snapshot* atau lock tabel.
   * **Saran:** Sebaiknya `backup_postgres.sh` membaca variabel `BACKUP_DATABASE_URL="${DIRECT_DATABASE_URL:-$DATABASE_URL}"` agar `pg_dump` memprioritaskan koneksi langsung/sesi (port `5432`) jika tersedia di `.env`.

---

### 4. Interaksi Edit Nominal Utang (`PUT /api/debts/{id}`) pada Utang yang Sudah `settled` (Bagian 2 F3 & Bagian 3 #7)

Pada F3 dan temuan #7 dijelaskan bahwa `update_debt` kini menjaga konsistensi status dua arah: jika utang berstatus `settled` tetapi setelah diedit ternyata `paid_amount < total_amount`, maka status otomatis kembali menjadi `active`.

* **Pertanyaan Verifikasi:**
  Di audit sebelumnya, terungkap bahwa pada *route* `PUT /api/debts/{debt_id}`, terdapat logika: *"Jika payload mengirimkan `status == 'settled'` dan sebelumnya belum settled, otomatis buat pembayaran pelunasan"*.
  Bagaimana jika utang **sudah berstatus `settled`** (misal `total = 500.000`, `paid = 500.000`), lalu di aplikasi Mobile pengguna mengedit `total_amount` menjadi `800.000` (sementara state *form* di UI Mobile masih mengirim `status: "settled"` di body JSON `PUT`)?
  * Apakah *route* `PUT /api/debts/{debt_id}` sudah mengabaikan field `status: "settled"` dari request body ketika `paid_amount < new_total_amount`, sehingga statusnya benar-benar turun menjadi `active` (dan tidak malah menolak request atau membuat transaksi pelunasan otomatis Rp 300.000 tanpa sengaja)?

---

### 5. Tiga Pertanyaan Operasional Kecil (Nice-to-Have untuk Jangka Panjang)

1. **Fitur *Unlink* / Ganti Akun Telegram:**
   Saat ini F4 sudah menangani proses `/link <kode>` dengan sangat aman. Namun, bagaimana jika nomor Telegram pengguna hangus/berganti dan mereka ingin melepas tautan Telegram lama dari aplikasi Mobile untuk menautkan akun Telegram baru? Apakah endpoint `POST /api/auth/telegram-link-token` dan `/link <kode>` mengizinkan penimpaan `telegram_user_id` lama pada akun Mobile yang sudah `telegram_linked = True`, atau perlu tombol **"Putuskan Tautan Telegram"** di halaman Pengaturan Mobile?
2. **Pembersihan Baris Kedaluwarsa di `telegram_link_codes`:**
   Kode lama milik pengguna yang sama memang dihapus saat pengguna meminta kode baru. Namun, jika ada pengguna yang meminta kode lalu tidak pernah mengetik `/link` di bot, baris tersebut akan tertinggal di tabel `telegram_link_codes`. Apakah saat `POST /api/auth/telegram-link-token` dipanggil, query-nya sekalian menghapus seluruh baris di tabel yang sudah melewati batas `expires_at < NOW()`?
3. **Penutupan Pool (`pool.close()`) saat *Shutdown*:**
   Saat proses FastAPI atau Bot Telegram di-restart lewat `systemd` (`systemctl restart finance-api`), apakah `ConnectionPool` milik `psycopg_pool` ditutup secara eksplisit pada akhir *lifespan* FastAPI dan *shutdown hook* Bot? Menutup *pool* dengan rapi mencegah koneksi menggantung (*zombie connections*) di sisi server Supabase saat Anda sering melakukan *re-deploy*.

---

Jika keempat poin teknis di atas (terutama **prefix `REPLACE` pada `source_key`** dan **keberadaan `recurring_transactions` di skrip migrasi**) sudah Anda pastikan aman, maka secara arsitektur dan kode, proyek ini **100% siap dinaikkan ke produksi Supabase**.