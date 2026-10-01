# 📱 Mobile App (Expo + React Native) & Backend (FastAPI) Setup Guide

Panduan menjalankan **Personal Finance Mobile App** berbasis **Expo + React Native (TypeScript)** dan **Python (FastAPI)**.

---

## 🏗 Struktur Arsitektur

1. **Backend (`/backend`)**:
   - Python 3.8+ / 3.11+ dengan **FastAPI**
   - Autentikasi JWT (Register, Login, Me)
   - Endpoint CRUD Transaksi & Quick Input text parser
   - Endpoint Laporan (Harian, Mingguan, Bulanan, Breakdown Kategori, Investasi)
   - Penyimpanan database SQLite (terintegrasi dengan data bot)

2. **Mobile App (`/mobile`)**:
   - **Expo SDK 52** + **React Native** + **TypeScript**
   - **Expo Router** (File-based navigation)
   - **Tema Dark Glassmorphism** (sesuai design system modern)
   - **Fitur Input Cepat Teks**: pengguna dapat mengetik teks bebas seperti `makan 25000` atau `gaji 5jt` langsung dari aplikasi mobile dengan preview instan dan tombol simpan
   - **Laporan & Analitik**: ringkasan sisa bersih, progres pengeluaran per kategori, dan riwayat transaksi

---

## 🚀 Cara Menjalankan

### Langkah 1: Jalankan Backend FastAPI

Buka terminal di root project atau via WSL:

```bash
cd backend
# Aktifkan virtual environment
source .venv/bin/activate    # (Linux/WSL) atau .venv\Scripts\activate (Windows)

# Jalankan server FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Swagger API Docs**: Buka browser di [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/](http://localhost:8000/)

---

### Langkah 2: Jalankan Mobile App (Expo)

Buka terminal kedua:

```bash
cd mobile

# Jalankan Expo dev server
npx expo start
```

Pilihan testing:
- **Di HP Android/iOS Fisik**: Install aplikasi **Expo Go** dari Google Play Store atau Apple App Store, lalu scan QR Code yang muncul di terminal.
- **Di Browser (Web)**: Tekan huruf `w` di terminal untuk membuka tampilan web responsif.
- **Di Android Emulator**: Tekan huruf `a` di terminal.
