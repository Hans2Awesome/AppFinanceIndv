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
`wallets` table archived as `wallets_archive`, indexes created). Set
`DATABASE_URL` to use PostgreSQL (Supabase) instead; see the README setup
section and `scripts/migrate_sqlite_to_postgres.py` for copying existing data.

### 2. Start the mobile app

```bash
cd mobile
cp .env.example .env
# Physical device: use your machine's LAN IP, not localhost
# EXPO_PUBLIC_API_URL=http://192.168.1.10:8000
# Google sign-in (Android native build only):
# EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=<web client id>.apps.googleusercontent.com
yarn install
npx expo start
```

Test options:

- **Physical device**: install Expo Go and scan the QR code. Email/password
  works here; Google controls stay hidden because the native module is absent.
- **Web**: press `w`.
- **Android emulator**: press `a`.
- **iOS simulator**: press `i` (macOS only).

### 2a. Google sign-in on Android

Google needs a development build (or an APK), not Expo Go.

1. In Google Cloud, create one **Web** OAuth client and one **Android** client
   for package `com.financeapp.mobile` with the SHA-1 of the signing certificate
   you actually build with. EAS preview/debug builds use a different keystore
   from Play App Signing, so register every fingerprint you ship.
2. Set the same Web client ID in the backend `GOOGLE_WEB_CLIENT_ID` and in the
   mobile build `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`. For a local build put it in
   `mobile/.env`; for EAS put it in the EAS environment used by that profile
   (`eas env:create`), not in git.
3. Replace the placeholder `iosUrlScheme` in `mobile/app.json` with the real
   reversed iOS client ID before any iOS work, and set an iOS bundle identifier
   when iOS ships. Android ignores that value, but the current config plugin
   refuses to prebuild without it.
4. Build and install:

```bash
npx eas-cli build --platform android --profile preview
# or, for a local development client:
npx expo prebuild --platform android
yarn android
```

The `development` EAS profile inherits the API URL in `eas.json`, which points at
the current deployed API. Override `EXPO_PUBLIC_API_URL` for that profile before
testing against a local backend, so a dev build never writes into production
data.

5. Sign in with Google, then check the existing password account flow still
   works. Linking Google is only offered in Settings for accounts that have a
   password and the same verified email.

Do not commit client secrets or signing keys. The Web client ID is public and
safe to ship; a Google client secret is not used by this flow.

### 3. Auth flow

1. Register or log in. The API returns an access token (30 min) and a refresh
   token (30 days).
2. Tokens are stored in SecureStore on native builds. On web they are kept in
   memory only, so a reload requires logging in again.
3. Any `401` triggers one refresh attempt; if that fails the session is cleared
   and the router returns to the login screen.