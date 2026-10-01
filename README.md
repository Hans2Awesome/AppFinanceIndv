# 💰 AppFinanceIndv — Personal Finance Management System

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Aplikasi pencatatan dan pengelolaan keuangan personal all-in-one berbasis **Mobile App (Expo + React Native)**, **Backend REST API (FastAPI)**, dan **Telegram Bot Tracker**.

---

## 🌟 Fitur Utama

### 📱 1. Mobile Application (Android & iOS)
- **Dashboard Ringkasan**: Tampilan modern sisa saldo bersih (*net balance*), total pemasukan, dan total pengeluaran.
- **Input Cepat (Quick Input Text)**: Ketik transaksi dengan format bahasa natural seperti:
  - `makan 25000`
  - `kopi 25k kemarin`
  - `gaji 5000000 bonus`
  - `invest btc 100000 dca`
  - Dilengkapi *live preview* dan tombol konfirmasi `Simpan` / `Batal`.
- **🤝 Fitur Hutang & Piutang (Debts & Receivables)**:
  - Pencatatan hutang (kewajiban bayar) dan piutang (hak tagih).
  - Pembayaran cicilan bertahap (*installment payments*) dengan riwayat pembayaran lengkap.
  - Progress bar visual pelunasan.
  - Indikator status otomatis: **Lunas**, **Segera Jatuh Tempo** (≤ 7 hari), dan **Lewat Jatuh Tempo**.
  - Widget ringkasan hutang & piutang langsung di dashboard utama.
- **📊 Laporan & Analitik**:
  - Filter laporan harian, mingguan, dan bulanan.
  - Visualisasi alokasi pengeluaran per kategori.
  - Laporan portofolio investasi.
- **🎨 Desain Modern Dark Theme**:
  - Glassmorphism dark UI yang elegan dan nyaman di mata.
  - Warna aksen tematik (*cyan* untuk hutang, *purple* untuk piutang, *emerald* untuk pemasukan, *rose* untuk pengeluaran).

---

### ⚡ 2. Backend REST API (FastAPI + SQLite)
- **Arsitektur Modular**: Terstruktur rapi dengan database layer, service layer, router, dan Pydantic schemas.
- **Autentikasi JWT**: Registrasi, login, dan proteksi endpoint berbasis bearer token.
- **Natural Language Parser**: Service pemrosesan teks bebas menjadi nominal, tanggal, kategori, dan catatan transaksi.
- **Manajemen Hutang & Piutang**: Endpoints CRUD lengkap dengan kalkulasi sisa hutang dan riwayat pembayaran cicilan.
- **Dokumentasi Interaktif**: Swagger UI otomatis di `/docs` dan ReDoc di `/redoc`.

---

### 🤖 3. Telegram Bot Tracker (`src/bot04/`)
- Chatbot Telegram untuk pencatatan transaksi secara instan langsung dari chat.
- Flow tombol interaktif dan inline keyboard.
- Perintah laporan cepat: `/today`, `/week`, `/month`, `/riwayat_pemasukan`, `/riwayat_pengeluaran`.

---

## 🛠️ Tech Stack

| Komponen | Teknologi |
|----------|-----------|
| **Mobile Frontend** | React Native, Expo SDK 52, TypeScript, Expo Router |
| **Icons & UI** | `@expo/vector-icons` (Ionicons), Custom Design System Tokens |
| **Backend API** | Python 3.10+, FastAPI, Pydantic, Uvicorn |
| **Database** | SQLite3 (dengan skema relasional transaksi, kategori, debts, dan payments) |
| **Autentikasi** | JWT (JSON Web Tokens), PBKDF2 / Bcrypt password hashing |
| **Telegram Bot** | Python Telegram Bot |

---

## 📁 Struktur Direktori

```text
AppFinanceIndv/
├── backend/                  # 🐍 Backend FastAPI & Database
│   ├── app/
│   │   ├── auth/             # Logika otentikasi JWT & password hashing
│   │   ├── database/         # Database connection, schema, & CRUD queries
│   │   │   ├── debts.py      # Layer database hutang & cicilan
│   │   │   ├── schema.py     # Inisialisasi tabel SQLite
│   │   │   └── ...
│   │   ├── models/           # Domain models & Pydantic request/response schemas
│   │   ├── reports/          # Agregator data laporan harian/mingguan/bulanan
│   │   ├── routes/           # REST API endpoints (auth, debts, transactions, reports)
│   │   ├── services/         # Quick input parser & business logic
│   │   └── main.py           # Entrypoint aplikasi FastAPI
│   ├── requirements.txt      # Dependency Python backend
│   └── tests/                # Automated API tests
│
├── mobile/                   # 📱 Expo + React Native Mobile App
│   ├── app/                  # Expo Router (File-based routing)
│   │   ├── (auth)/           # Halaman login & register
│   │   ├── (tabs)/           # Tab utama: Dashboard, Add, Debts, Reports, Settings
│   │   └── _layout.tsx       # Root navigation layout
│   ├── components/           # Komponen UI: DebtCard, DebtSummaryCard, QuickInputBar, dll.
│   ├── services/             # Integrasi HTTP API (Axios / Fetch)
│   ├── types/                # TypeScript interface definitions
│   ├── utils/                # Format Rupiah, tema warna, dsb.
│   └── package.json          # Dependencies Expo
│
├── src/                      # 🤖 Telegram Bot Source Code
│   └── bot04/
│       ├── bot/              # Handlers pesan & callback query
│       ├── database/         # SQLite storage untuk bot
│       └── services/         # Text parser & helper
│
├── docs/                     # 📚 Dokumentasi tambahan
│   └── mobile-quickstart.md  # Panduan cepat setup mobile app
├── .gitignore                # Konfigurasi filter Git
└── README.md                 # Dokumentasi utama proyek
```

---

## 🚀 Panduan Menjalankan Aplikasi

### 1. Menjalankan Backend (FastAPI)

Pastikan Python 3.10+ sudah terinstal di sistem Anda.

```bash
# 1. Masuk ke direktori backend
cd backend

# 2. Buat dan aktifkan virtual environment
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS / WSL:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Buat file .env
copy .env.example .env   # (Windows)
# atau: cp .env.example .env (Linux/Mac)

# 5. Jalankan server FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **API Documentation (Swagger)**: Buka [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/](http://localhost:8000/)

---

### 2. Menjalankan Mobile App (Expo)

Pastikan [Node.js](https://nodejs.org/) (versi LTS 18+ atau 20+) sudah terinstal.

```bash
# 1. Masuk ke direktori mobile
cd mobile

# 2. Install dependencies
npm install
# atau: yarn install

# 3. Jalankan Expo Development Server
npx expo start
```

**Pilihan Pengujian:**
- **Smartphone Fisik (Android/iOS)**: Buka aplikasi **Expo Go** di ponsel Anda, lalu scan QR Code yang muncul di terminal.
- **Web Browser**: Tekan tombol `w` di terminal untuk membuka antarmuka web responsif.
- **Android Emulator**: Tekan tombol `a` di terminal.
- **iOS Simulator**: Tekan tombol `i` di terminal (khusus macOS).

> **Catatan Konfigurasi API Mobile:**  
> Jika menjalankan Expo di HP fisik, sesuaikan URL backend pada file `mobile/services/api.ts` ke alamat IP lokal komputer Anda (contoh: `http://192.168.1.10:8000`), bukan `localhost`.

---

### 3. Menjalankan Telegram Bot (Opsional)

```bash
# 1. Salin konfigurasi environment bot
copy .env.example .env

# 2. Masukkan BOT_TOKEN dari @BotFather ke file .env

# 3. Jalankan bot
python -m bot04.main
```

---

## 📡 Ringkasan Endpoints API (Hutang & Piutang)

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/debts/summary` | Ringkasan total hutang, total piutang, posisi bersih, dan counter |
| `GET` | `/debts/` | Mengambil daftar hutang/piutang (dengan filter status & tipe) |
| `POST` | `/debts/` | Membuat data hutang atau piutang baru |
| `GET` | `/debts/{debt_id}` | Mendapatkan detail data hutang beserta histori cicilan |
| `PUT` | `/debts/{debt_id}` | Memperbarui data hutang |
| `DELETE` | `/debts/{debt_id}` | Menghapus data hutang |
| `POST` | `/debts/{debt_id}/payments` | Mencatat pembayaran cicilan hutang/piutang |
| `GET` | `/debts/{debt_id}/payments` | Mengambil riwayat transaksi pembayaran cicilan |

---

## 🔒 Keamanan & Praktik Terbaik

- File konfigurasi rahasia seperti `.env` dan file database lokal (`*.sqlite3`, `*.db`) sudah diatur untuk diabaikan oleh Git melalui file [`.gitignore`](.gitignore).
- Password pengguna dienkripsi dengan standar industri (hashing dengan salt).
- Akses data transaksi dan hutang terisolasi per pengguna yang terautentikasi.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah lisensi **[Apache License 2.0](LICENSE)**.

Anda memiliki kebebasan untuk:
- Menggunakan kode ini untuk keperluan pribadi maupun **komersial**.
- Memodifikasi, mengembangkan, dan mendistribusikan salinan kode sumber atau bentuk biner.
- Mendapatkan lisensi hak paten eksplisit dari para kontributor.

Dengan ketentuan:
- Menyertakan salinan lisensi [**Apache-2.0**](LICENSE) dan pemberitahuan hak cipta (*copyright notice*) asli.
- Menyertakan catatan perubahan (*prominent notices*) jika Anda melakukan modifikasi pada file kode.
- Software ini disediakan *"AS IS"* tanpa jaminan atau garansi dalam bentuk apa pun.

Untuk ketentuan dan klausul hukum selengkapnya, silakan lihat file [LICENSE](LICENSE).
