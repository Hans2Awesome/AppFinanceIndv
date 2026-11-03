# Tanggapan Audit Kritis Pra-Produksi dan Hasil Verifikasi

Dokumen ini menjawab `audit_kritis_pra_produksi_dan_verifikasi_implementasi.md`.
Setiap klaim diuji langsung di kode dan dengan skrip reproduksi, bukan hanya
dibaca. Hasilnya: dua klaim salah premis, satu klaim sudah benar sejak awal,
dan tiga klaim menunjuk masalah nyata yang sudah diperbaiki di commit terbaru.

- Tanggal verifikasi: 3 November 2026
- Basis sebelum perbaikan: `32080ef`
- Status: semua temuan yang valid sudah ditutup, plus tiga item operasional

---

## 1. Ringkasan Penilaian Klaim

| # | Klaim audit | Hasil uji | Tindakan |
| :--- | :--- | :--- | :--- |
| 1 | `REPLACE(source_key, ':bot:', ':owner:')` merusak `schedule_id` | **Premis salah**, risiko nyata tetap ada | Diperbaiki: rebase per prefix |
| 2 | `recurring_transactions` tidak ikut migrasi | **Salah**, tabel ada dan disalin | Tidak ada, sudah benar |
| 3a | Dump kosong lolos cek `-s` | **Benar**, file 20 byte tertinggal | Diperbaiki: tulis `.part` + cek isi |
| 3b | `pg_dump` lewat pooler 6543 | **Benar**, berisiko gagal | Diperbaiki: pakai `DIRECT_DATABASE_URL` |
| 4 | PUT `settled` + total naik membuat pelunasan otomatis | **Sudah benar**, teruji | Ditambah tes regresi |
| 5a | Belum ada unlink Telegram | **Benar** | Diperbaiki: API + bot + UI |
| 5b | Kode kedaluwarsa menumpuk | **Benar** | Diperbaiki: prune saat buat kode |
| 5c | Pool tidak ditutup saat shutdown | **Benar** | Diperbaiki: lifespan API + bot |

---

## 2. Koreksi terhadap Klaim Audit

### 2.1. Klaim 1: mekanisme `REPLACE` tidak seperti yang dideskripsikan

Audit menulis bahwa kode memakai `REPLACE(source_key, ':bot:', ':owner:')`.
Kode sebenarnya memakai parameter, yaitu `REPLACE(source_key, ?, ?)` dengan
nilai `f":{bot_id}:"` dan `f":{user_id}:"` (`finance_core/db/users.py`).
Hasil akhirnya sama-sama `REPLACE(source_key, ':2:', ':1:')`, jadi
kekhawatirannya tetap relevan. Perbedaannya hanya pada penyajian.

Namun **contoh kerusakan di audit tidak terjadi**. Audit menulis bahwa
`REPLACE('recurring:2:2:2026-11-02', ':2:', ':1:')` menghasilkan
`recurring:1:1:2026-11-02`. Itu keliru: `REPLACE` mengganti dari kiri ke kanan
dan tidak memindai ulang hasil yang sudah diganti. Hasil sebenarnya adalah
`recurring:1:2:2026-11-02`, sehingga `schedule_id` tetap `2`.

Bukti reproduksi:

```text
'recurring:2:2:2026-11-02'  -> 'recurring:1:2:2026-11-02'
'recurring:2:12:2026-11-02' -> 'recurring:1:12:2026-11-02'
'recurring:2:2:2:2026-11-02'-> 'recurring:1:2:1:2026-11-02'
'debt:2:2'                  -> 'debt:1:2'
'debt_payment:2:7'          -> 'debt_payment:1:7'
```

**Tetapi ada bug nyata di baris ketiga.** Baris itu membuktikan pola
`":<bot_id>:"` bisa mengganti segmen lain, bukan hanya user id. Untuk
`source_key` yang punya dua segmen `:2:` berdampingan, hasilnya rusak.

### 2.2. Klaim 2: `recurring_transactions` sudah ada di skrip migrasi

Tabel ini ada di daftar `TABLES` sejak awal (`scripts/migrate_sqlite_to_postgres.py:83`).
Log di laporan sebelumnya terpotong oleh `tail`, sehingga baris
`recurring_transactions` tidak ikut tercetak. Itu kesalahan penyajian laporan
saya, bukan kesalahan kode.

Bukti: menjalankan migrasi penuh pada `bot04.sqlite3` menghasilkan

```text
recurring_transactions: 0 row(s) copied
verify recurring_transactions: sqlite=0 postgres=0 ok
```

Angkanya `0` karena database asli memang belum punya jadwal berulang, bukan
karena tabelnya dilewati.

### 2.3. Klaim 3a: `set -euo pipefail` sudah ada

Skrip memang sudah memakai `set -euo pipefail` sejak versi sebelumnya. Jadi
kekhawatiran "pastikan sudah dipasang" sudah terpenuhi.

**Tapi sisa masalahnya nyata**, dan audit benar menunjuk ke arah itu. Walaupun
skrip keluar dengan kode error, file `.sql.gz` berukuran 20 byte tetap
tertinggal di disk:

```text
pg_dump: error: connection failed
exit=1
-rw-r--r-- 1 root root 20 ... fake.sql.gz
size check PASSES (bug)
```

Cek `[ ! -s "$target" ]` lolos karena 20 byte dianggap "tidak kosong". Akibatnya
cron bisa meninggalkan arsip rusak yang tampak valid.

### 2.4. Klaim 4: PUT pada utang `settled` sudah aman

Sudah diuji end-to-end lewat API sebelum ada perubahan apa pun:

```text
after settle: 200 settled 500000 500000
after raise:  200 active  500000 800000
payments:     [(1, 500000)]
```

Status turun ke `active`, `paid_amount` tidak berubah, dan **tidak** ada
transaksi pelunasan otomatis Rp 300.000. Penyebabnya: cabang pelunasan otomatis
hanya berjalan bila `payload.status == "settled"` **dan** `existing.status !=
"settled"`. Untuk utang yang sudah settled, cabang itu dilewati, lalu
`update_debt` menurunkan status karena `paid_amount < new_total`.

Perilaku ini sekarang dikunci oleh tes
`test_update_debt_keeps_status_consistent_with_amounts`.

---

## 3. Perbaikan yang Dikerjakan

### 3.1. Rebase `source_key` per prefix (klaim 1)

Sebelum:

```python
UPDATE transactions
SET user_id = ?, source_key = REPLACE(source_key, ?, ?)
WHERE user_id = ?          -- pola ":<bot_id>:" di mana pun
```

Sesudah:

```python
for prefix in ("debt", "debt_payment", "recurring"):
    # buang baris kas bot yang kuncinya bentrok dengan milik pemilik
    # lalu ganti hanya "<prefix>:<bot_id>:" -> "<prefix>:<user_id>:"
```

Tiga efek:

1. Hanya segmen user id yang berubah; id jadwal dan id pembayaran aman.
2. Transaksi bot tanpa `source_key` (input manual) tetap ikut pindah lewat satu
   `UPDATE` terpisah. Versi pertama perbaikan saya melewatkan ini dan
   menggagalkan tes lama; sudah diperbaiki.
3. Baris kas bot yang kuncinya sudah dipakai pemilik dihapus lebih dulu.
   Tanpa ini, merge gagal karena `source_key` berindeks unik:

```text
MERGE FAILED: IntegrityError UNIQUE constraint failed: transactions.source_key
```

Bug ketiga ini tidak disebut di audit. Saya temukan saat menguji skenario
"pemilik dan bot sama-sama punya `debt:<id>:5`". Sekarang merge berhasil dan
hanya menyisakan baris milik pemilik.

### 3.2. Skrip backup (klaim 3)

Perubahan pada `scripts/backup_postgres.sh`:

1. Dump ditulis ke `<target>.part`, baru di-`mv` setelah lolos validasi. File
   gagal tidak pernah memakai nama final.
2. Validasi isi, bukan hanya ukuran:
   `gzip -dc "$partial" | grep -q .` memastikan arsip benar-benar berisi SQL.
3. `BACKUP_URL="${DIRECT_DATABASE_URL:-${DATABASE_URL:-}}"`, jadi `pg_dump`
   memakai sesi langsung (port 5432) bila tersedia.
4. `trap cleanup EXIT` menghapus `.part` pada semua jalur keluar.

Simulasi dump kosong:

```text
: | gzip > partial
-> EMPTY DETECTED
```

### 3.3. Unlink Telegram (klaim 5a)

Tiga permukaan ditambahkan:

1. `unlink_telegram_account()` di `finance_core/db/users.py`: kosongkan
   `telegram_user_id`, hapus kode tautan yang belum terpakai, data keuangan
   tidak disentuh.
2. `DELETE /api/auth/telegram-link` di `backend/app/routes/auth.py`.
3. `/unlink` di bot dan tombol "Putuskan tautan Telegram" di halaman Pengaturan
   mobile. Tombol hanya muncul saat `telegram_linked` bernilai true.

Setelah unlink, penautan ke akun Telegram baru berfungsi: `link_telegram_account`
sudah meng-update `telegram_user_id` di baris akun, jadi tidak perlu jalur
khusus. Ini diuji di `test_unlink_telegram_keeps_data_and_clears_telegram_id`.

Catatan desain: `/unlink` hanya bekerja untuk akun Mobile (baris dengan
`email`). Baris bot murni tidak punya akun Mobile, jadi bot menjawab bahwa
tidak ada tautan yang perlu dilepas, bukan menghapus data.

### 3.4. Prune kode kedaluwarsa (klaim 5b)

`create_telegram_link_code` sekarang menghapus semua baris dengan
`expires_at < now` sebelum menyisipkan kode baru. Kode kedaluwarsa sudah tidak
bisa dipakai, jadi aman dihapus, dan tabel tidak menumpuk baris dari pengguna
yang minta kode tapi tidak pernah mengirimkannya ke bot.

### 3.5. Penutupan pool saat shutdown (klaim 5c)

1. API: `close_pools()` dipanggil di blok `finally` lifespan, setelah task
   scheduler dibatalkan (`backend/app/main.py`).
2. Bot: `application.post_shutdown = _close_pools_on_shutdown`
   (`src/bot04/bot/app.py`).

Efek: `systemctl restart` tidak lagi meninggalkan koneksi menggantung di sisi
Supabase sampai server memutusnya sendiri.

---

## 4. Berkas yang Berubah

| Berkas | Perubahan |
| :--- | :--- |
| `finance_core/db/users.py` | Rebase `source_key` per prefix, buang baris kas bentrok, prune kode kedaluwarsa, `unlink_telegram_account` |
| `backend/app/routes/auth.py` | `DELETE /api/auth/telegram-link` |
| `backend/app/main.py` | `close_pools()` di akhir lifespan |
| `src/bot04/bot/app.py` | `/unlink`, `post_shutdown` untuk pool, import baru |
| `scripts/backup_postgres.sh` | Tulis `.part`, validasi isi, `DIRECT_DATABASE_URL` |
| `mobile/app/(tabs)/settings.tsx` | Tombol putuskan tautan Telegram |
| `mobile/services/auth.ts` | `unlinkTelegram()` |
| `docs/deploy-supabase.md` | Backup pakai DSN direct, verifikasi 6 tabel, catatan pool |
| `tests/test_users_repository.py` | 4 tes baru |
| `backend/tests/test_api_auth.py` | 1 tes baru |
| `tests/test_bot_app.py`, `tests/test_bot_commands.py` | Perintah `unlink` |

---

## 5. Hasil Verifikasi

```text
ruff check .                          All checks passed
pytest tests/ backend/tests           233 passed, 5 skipped
POSTGRES_TEST_URL=... pytest          5 passed
npx tsc --noEmit (mobile)             bersih
```

Teknis:

| Skenario | Sebelum | Sesudah |
| :--- | :--- | :--- |
| `recurring:2:2:...` saat merge | id jadwal berisiko berubah | `recurring:1:2:...`, id jadwal utuh |
| Kunci kas bentrok pemilik vs bot | `IntegrityError`, merge gagal | merge sukses, baris pemilik dipertahankan |
| Transaksi bot tanpa `source_key` | tertinggal | ikut pindah |
| Dump gagal | arsip 20 byte tertinggal | file dihapus, exit non-zero |
| Kode kedaluwarsa | menumpuk | terhapus saat buat kode baru |
| Pool saat restart | koneksi menggantung | ditutup eksplisit |

Migrasi ulang ke PostgreSQL lokal: 95 baris, semua `verify ... ok`, termasuk
`recurring_transactions`, dan idempoten saat dijalankan dua kali.

---

## 6. Tanggapan Lanjutan di Luar Audit

Hal-hal yang audit belum sebut, tapi perlu diputuskan sebelum produksi:

1. **ID jadwal masih bisa bertabrakan secara teori setelah rebase.** Kunci
   `recurring:<user>:<schedule>:<tanggal>` menjadi unik setelah baris bot
   dihapus, tetapi `recurring_transactions` milik bot yang dipindah ke pemilik
   bisa punya id bentrok kalau kedua sisi punya id yang sama. Saat ini belum
   terjadi karena SQLite memakai satu urutan id global. Kalau nanti data bot
   dan Mobile pernah dipisah ke dua database lalu digabung manual, ini perlu
   pengecekan sebelum merge.
2. **Unlink tidak menghapus riwayat Telegram.** Itu memang disengaja: data
   keuangan milik akun, bukan milik Telegram. Yang dilepas hanya identitas.
3. **`pg_dump` versi klien harus >= versi server.** Ini masih berlaku dan belum
   bisa diotomatiskan dari repo. Catat di playbook deploy VPS.
4. **Backup masih di disk VPS.** Skrip sudah aman sekarang, tetapi tetap hilang
   bersama VPS. Tambahkan `rclone copy` setelah baris `mv`.
5. **Rate limiter in-process.** Tetap aman untuk satu worker. Multi-worker
   butuh Redis; ini bukan regresi, hanya batas yang diketahui.

---

## 7. Kesimpulan

Dari sembilan klaim yang diperiksa, tiga sudah benar sebelum audit (klaim 2,
3a sebagian, dan 4), tiga menunjuk masalah nyata yang sekarang diperbaiki
(3a sisa file, 3b, 5c), dan tiga lainnya adalah item operasional yang belum ada
dan sekarang ditambahkan (5a, 5b, dan perbaikan rebase meski premisnya salah).

Satu bug tambahan (kunci `source_key` bentrok saat merge) ditemukan di luar
audit dan ikut ditutup. Dengan perubahan ini, syarat audit "100% siap
dinaikkan ke produksi" terpenuhi secara kode. Sisa pekerjaan hanya operasional:
membuat project Supabase, mengisi `.env` VPS, dan menjalankan urutan di
`docs/deploy-supabase.md`.
