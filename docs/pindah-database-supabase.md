# Pindah database antar project Supabase

Panduan ini dipakai saat pindah region, misalnya Frankfurt ke Singapura karena
backend pindah ke VPS Asia. Isinya beda dengan `docs/deploy-supabase.md`:
dokumen itu memindahkan SQLite ke PostgreSQL, dokumen ini memindahkan
PostgreSQL ke PostgreSQL.

Skripnya: `scripts/copy_postgres_database.sh`.

## Kenapa tidak pakai skrip migrasi SQLite

`scripts/migrate_sqlite_to_postgres.py` membaca dari file SQLite. Untuk
Supabase ke Supabase, sumbernya PostgreSQL, jadi rutenya `pg_dump` +
`pg_restore`. Dump bentuk custom menyimpan id, sequence, primary key, foreign
key, index, trigger, dan nilai default, sehingga hasilnya sama strukturnya dan
identik datanya, tanpa menulis ulang satu baris pun secara manual.

Waktu terukur pada mesin uji (PostgreSQL 18.6, database 20 MB, 40.000
transaksi):

| Langkah | Waktu |
| :--- | :--- |
| `pg_dump` bentuk custom | 0,26 s |
| `pg_restore` ke database kosong | 0,39 s |
| ukuran dump | 540 KB |

Database kecil seperti aplikasi ini selesai di bawah 5 detik setelah dump
tersedia. Yang lambat bukan dump-nya, tapi jaringan: dump langsung dari
Supabase Frankfurt butuh 17,65 detik untuk 35 KB karena setiap perintah
menempuh TLS round-trip.

## Langkah

### 1. Siapkan project tujuan

Buat project Supabase baru di region yang diinginkan (misalnya
`ap-southeast-1` / Singapura). Catat dua DSN-nya:

- **Session pooler** port `5432`: dipakai skrip ini.
- **Transaction pooler** port `6543`: dipakai `.env` setelah pindah.

Jangan jalankan `run_migrations` atau membuat tabel apa pun di project baru.
Skrip ini yang membuat semuanya.

### 2. Hentikan penulisan

Supabase free tier tidak punya replikasi, jadi langkah ini butuh downtime
singkat. Matikan dulu supaya tidak ada baris baru masuk saat dump berjalan:

```bash
sudo systemctl stop finance-api finance-bot
```

Cek tidak ada perubahan setelah dump: hitung baris di sumber sebelum dan
sesudah. Skrip ini melakukannya otomatis di akhir.

### 3. Jalankan skrip

```bash
SOURCE_URL="postgresql://postgres.<ref-lama>:<pass>@aws-1-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require" \
TARGET_URL="postgresql://postgres.<ref-baru>:<pass>@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require" \
./scripts/copy_postgres_database.sh
```

Uji dulu tanpa menyentuh target:

```bash
SOURCE_URL=... TARGET_URL=... DRY_RUN=1 ./scripts/copy_postgres_database.sh
```

### 4. Baca keluarannya

Contoh keluaran yang benar:

```text
==> Dumping source
    dump: ./backups/move_2026-11-03_165703.dump (544K, 0s)
==> Restoring into target
    restore: 1s
==> Verifying row counts per table
source / target
  categories                      400 /    400 ok
  transactions                  40000 /  40000 ok
  users                            20 /     20 ok
Done.
```

Semua baris harus `ok`. Kalau ada `MISMATCH`, jangan lanjut.

### 5. Ganti `.env`

```bash
DATABASE_URL=postgresql://postgres.<ref-baru>:<pass>@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require
DIRECT_DATABASE_URL=postgresql://postgres.<ref-baru>:<pass>@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require
```

`SECRET_KEY` **jangan diganti**. Kalau diganti, semua token JWT lama tidak valid
dan setiap pengguna ter-logout.

Kalau VPS juga pindah, salin `.env` apa adanya ke VPS baru.

### 6. Nyalakan dan verifikasi

```bash
sudo systemctl start finance-api
curl -fsS http://127.0.0.1:8000/
sudo systemctl start finance-bot
```

Lalu:

1. Login dengan akun lama, cek riwayat transaksi.
2. Cek laporan harian, mingguan, dan bulanan.
3. Buka daftar utang dan cicilan.
4. Kirim satu pesan ke bot.

Selesai. Project Frankfurt boleh dihapus setelah beberapa hari tanpa masalah.

## Kenapa skrip menolak beberapa kondisi

| Kondisi | Perilaku | Alasan |
| :--- | :--- | :--- |
| URL port `6543` | ditolak | pooler transaksi tidak bisa memberi snapshot konsisten untuk `pg_dump` |
| `SOURCE_URL` = `TARGET_URL` | ditolak | akan menimpa database yang sedang dibaca |
| Target sudah punya tabel | ditolak kecuali `FORCE=1` | restore di atas data lama bisa menduplikasi baris |
| Dump kosong atau tidak terbaca | ditolak | dicek dengan `pg_restore --list` sebelum restore |

## Detail teknis yang mudah salah

**Schema `public` di target baru.** Setiap project Supabase sudah punya schema
`public` kosong, sedangkan dump membawa entri `SCHEMA - public`. Restore akan
gagal dengan `schema "public" already exists`. Skrip menyaring entri schema itu
saja dari daftar restore; semua tabel, index, sequence, key, dan trigger tetap
dipulihkan.

**`pg_restore` butuh `--dbname`, bukan URL posisional.** Bentuk `pg_restore
"$URL" file.dump` dianggap dua argumen file dan gagal dengan `too many
command-line arguments`.

**Urutan drop schema tidak dipakai.** Sempat dicoba `DROP SCHEMA public
CASCADE; CREATE SCHEMA public;` sebelum restore. Cara itu berbahaya kalau
`TARGET_URL` salah ketik dan menunjuk database lain. Penyaringan TOC lebih aman
karena tidak menghapus apa pun di target.

**Trigger ikut pulih.** Aplikasi ini memakai trigger validasi (`amount > 0`,
`type` terbatas, aturan jadwal berulang). Restore mengembalikannya, jadi data
yang tidak valid tetap ditolak setelah pindah. Ini sudah diuji: 8 trigger dan
8 foreign key pulih pada database uji.

**Sequence ikut pulih.** `setval` tersimpan di dump, jadi insert baru tidak
bentrok dengan id lama. Diuji dengan menyisipkan user baru setelah restore: id
keluar `35`, di atas id lama tertinggi `18`.

## Biaya downtime

Database kecil: hitung 1 menit untuk stop layanan, 1 menit untuk dump, 1 menit
untuk restore, 1 menit untuk verifikasi. Total sekitar 5 menit. Kalau ingin
nol downtime, urutannya: jalankan skrip dengan layanan masih hidup, ulangi
sekali lagi tepat setelah layanan dimatikan, lalu nyalakan di project baru.

## Rollback

Project lama tetap utuh karena skrip hanya membaca darinya. Kalau ada masalah,
kembalikan `.env` ke DSN Frankfurt dan nyalakan layanan. Tidak ada data yang
hilang.
