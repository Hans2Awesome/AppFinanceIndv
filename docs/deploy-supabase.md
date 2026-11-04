# Go-live Supabase: urutan deploy

Urutan ini wajib diikuti. Menjalankan bot sebelum skema siap akan gagal dengan
error tabel tidak ditemukan, dan menyalakan API dua kali saat migrasi berjalan
bisa membuat dua proses berebut lock.

## 1. Siapkan kredensial

1. Buat project Supabase, ambil **transaction pooler** DSN (port `6543`,
   `?sslmode=require`). Ini dipakai API dan bot sehari-hari.
2. Ambil juga **direct/session** DSN (port `5432` pada host database direct).
   Ini hanya dipakai skrip migrasi data, karena DDL dan penyalinan data harus
   berjalan dalam satu sesi utuh.

## 2. Hentikan layanan lama

```bash
sudo systemctl stop finance-api finance-bot
```

Pastikan `bot04.sqlite3` sudah di-backup sebelum menyentuh apa pun:

```bash
cp bot04.sqlite3 "bot04.sqlite3.$(date +%F).bak"
```

## 3. Isi environment

Di `.env` VPS (bukan di repo):

```bash
DATABASE_URL=postgresql://postgres.<ref>:<password>@<region>.pooler.supabase.com:6543/postgres?sslmode=require
SECRET_KEY=<minimal 32 karakter acak>
ENVIRONMENT=production
CORS_ORIGINS=https://<domain-mobile-web>
```

`ENVIRONMENT=production` menolak start bila `DATABASE_URL` kosong atau
`CORS_ORIGINS` masih `*`. Ini disengaja: API **dan** bot gagal keras, bukan
diam-diam menulis ke `bot04.sqlite3` lokal. `/docs` dan `/openapi.json` juga
mati di mode ini.

## 4. Buat skema dan salin data

Pakai DSN **direct** (port 5432) untuk langkah ini:

```bash
python scripts/migrate_sqlite_to_postgres.py \
  --database-url "postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres"
```

Skrip menyalin id asli, melewati baris yang sudah ada, mereset sequence, lalu
memverifikasi jumlah baris per tabel. Hentikan proses bila ada `MISMATCH`.

## 5. Nyalakan API lebih dulu

```bash
sudo systemctl start finance-api
curl -fsS http://127.0.0.1:8000/
```

API menjalankan `run_migrations` saat startup, jadi skema pasti berada di versi
terbaru sebelum bot menyentuh database.

## 6. Nyalakan bot

```bash
sudo systemctl start finance-bot
```

Bot tidak menjalankan migrasi. Bot hanya membuka koneksi per pesan dari pool,
jadi ia aman dijalankan setelah API sehat.

## 7. Verifikasi pasca-deploy

1. Login web/Android dengan akun lama, cek riwayat transaksi.
2. Kirim satu pesan ke bot, pastikan transaksi muncul di aplikasi setelah
   akun ditautkan lewat `/link <kode>`.
3. Cek `SELECT COUNT(*)` pada `users`, `categories`, `transactions`, `debts`,
   `debt_payments`, dan `recurring_transactions` dibanding angka dari SQLite.
   Skrip migrasi sudah mencetak baris `verify <tabel>`; semua harus `ok`.
4. Pastikan `systemctl restart finance-api` tidak meninggalkan koneksi
   menggantung di dashboard Supabase; pool ditutup di akhir lifespan.
5. Cek RLS dan trigger sudah terpasang (migrasi v5):

```sql
SELECT relname, relrowsecurity FROM pg_class
WHERE relname IN ('users','categories','transactions','debts',
                  'debt_payments','recurring_transactions','telegram_link_codes');
-- semua harus relrowsecurity = true
```

Supabase Security Advisor juga tidak boleh lagi melaporkan *RLS Disabled in
Public*. Fungsi API dan bot tidak terpengaruh karena role `postgres` punya
`BYPASSRLS`.

## 8. Backup mingguan

```bash
chmod +x scripts/backup_postgres.sh
0 3 * * 0 DATABASE_URL="postgresql://...:6543/..." DIRECT_DATABASE_URL="postgresql://...:5432/..." /path/to/scripts/backup_postgres.sh >> /var/log/finance-backup.log 2>&1
```

Skrip menulis `backups/finance_YYYY-MM-DD.sql.gz` dan menghapus dump lebih tua
dari `RETENTION_DAYS` (default 30 hari).

Set `DIRECT_DATABASE_URL` (port `5432`). `pg_dump` butuh satu sesi utuh untuk
snapshot yang konsisten dan lock tabel; transaction pooler (`6543`) tidak
menjamin itu. Skrip memakai `DIRECT_DATABASE_URL` bila ada, dan baru jatuh ke
`DATABASE_URL` bila tidak.

Dump ditulis ke `<nama>.part` lebih dulu. Bila `pg_dump` gagal, atau hasilnya
tidak berisi SQL, skrip hapus file sementara itu dan keluar dengan kode error,
jadi cron tidak pernah meninggalkan arsip kosong berukuran ~20 byte.

## Rollback

Bila migrasi gagal di tengah jalan, API dan bot tetap dalam keadaan berhenti.
SQLite asli tidak pernah ditulis oleh skrip migrasi, jadi rollback cukup
mengosongkan `DATABASE_URL` dan menyalakan ulang layanan lama:

```bash
sudo systemctl start finance-api finance-bot
```

Skrip migrasi bersifat idempoten dan aman dijalankan ulang setelah penyebab
kegagalan diperbaiki.
