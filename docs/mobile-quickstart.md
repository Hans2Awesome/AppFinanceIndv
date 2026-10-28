# 📱 Mobile app and API: local setup

The mobile app and the FastAPI backend run as two processes. The app has no
compiled-in server address: it reads `EXPO_PUBLIC_API_URL` at build time.

---

## One command (backend + tunnel + Expo + QR code)

```bash
python3 scripts/run_app.py
```

The script starts the API, opens a Cloudflare quick tunnel, starts Expo Metro
with `EXPO_PUBLIC_API_URL` pointing at the tunnel, and prints a QR code for Expo
Go. It never edits files in `mobile/`.

Windows shortcuts: double-click [`start.bat`](../start.bat) or run
`.\start.ps1`.

---

## Manual setup

### 1. Start the API

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" -r requirements-dev.txt

cd backend
cp .env.example .env      # set SECRET_KEY
cd ..
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/

The schema is migrated once at startup. Existing SQLite files from the old
bot-only schema are upgraded in place (email/password columns added, the legacy
`wallets` table archived as `wallets_archive`, indexes created).

### 2. Start the mobile app

```bash
cd mobile
cp .env.example .env
# Physical device: use your machine's LAN IP, not localhost
# EXPO_PUBLIC_API_URL=http://192.168.1.10:8000
yarn install
npx expo start
```

Test options:

- **Physical device**: install Expo Go and scan the QR code.
- **Web**: press `w`.
- **Android emulator**: press `a`.
- **iOS simulator**: press `i` (macOS only).

### 3. Auth flow

1. Register or log in. The API returns an access token (30 min) and a refresh
   token (30 days).
2. Tokens are stored in SecureStore on native builds. On web they are kept in
   memory only, so a reload requires logging in again.
3. Any `401` triggers one refresh attempt; if that fails the session is cleared
   and the router returns to the login screen.