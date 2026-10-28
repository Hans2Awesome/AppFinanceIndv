# 💰 AppFinanceIndv — Personal Finance Management System

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

One repository, three clients, one domain layer:

- **Mobile app** — Expo + React Native + TypeScript
- **REST API** — FastAPI + Pydantic + SQLite
- **Telegram bot** — python-telegram-bot

`finance_core/` holds the shared domain: schema migrations, repositories,
quick-input parsing and report aggregation. The API and the bot are thin
adapters over it, so there is exactly one implementation of the schema and one
of every query.

---

## Repository layout

```
finance_core/          Shared domain: db/, services/, reports/, timezones.py
backend/app/           FastAPI app: routes/, auth/, models/schemas.py
src/bot04/             Telegram bot: bot/ handlers, bot-only services
mobile/                Expo app: app/ routes, components/, services/
PRODUCT.md             Product context for the mobile app
DESIGN.md              Visual world and design tokens ("the ledger")
tests/                 Bot + shared-core tests
backend/tests/         API tests
docs/                  Architecture notes and task plans
```

---

## 🛠️ Tech stack

| Component | Technology |
|-----------|------------|
| Mobile | React Native, Expo SDK 58, TypeScript, Expo Router |
| Backend | Python 3.11+, FastAPI, Pydantic v2, Uvicorn |
| Database | SQLite (WAL, versioned migrations, indexes) |
| Auth | JWT access + refresh tokens, bcrypt password hashing |
| Bot | python-telegram-bot 21 |

---

## 🚀 Setup

### 1. Shared Python environment

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]" -r requirements-dev.txt
cp .env.example .env
```

### 2. Backend API

```bash
cd backend
cp .env.example .env
# Required: SECRET_KEY (no default is shipped)
python -c "import secrets; print(secrets.token_urlsafe(48))"
cd ..
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/
- Migrations run once at startup and are recorded in `schema_migrations`.

`SECRET_KEY` has **no fallback value**. The API refuses to start without it.

### 3. Mobile app

```bash
cd mobile
cp .env.example .env       # set EXPO_PUBLIC_API_URL
yarn install
npx expo start
```

`EXPO_PUBLIC_API_URL` is the only place the API host is configured. On a
physical device use your machine's LAN IP, for example
`EXPO_PUBLIC_API_URL=http://192.168.1.10:8000`. There is no hardcoded tunnel URL
in the source tree.

### 4. Telegram bot (optional)

```bash
cp .env.example .env
# Set BOT_TOKEN from @BotFather
python -m bot04.main
```

Quick input examples:

- `makan 25000`
- `kopi 25k kemarin`
- `invest btc 100000 dca mingguan`

History commands page through transactions **10 data per halaman**, ordered
**terbaru dulu**:

- `/riwayat_pemasukan`
- `/riwayat_pengeluaran`

Other commands: `/today`, `/week`, `/month`, `/report`, `/help`.

Dry run (loads config, does not poll Telegram):

```bash
python -m bot04.main --dry-run
```

---

## 🧪 Tests

```bash
pytest
```

`pytest` runs both suites (`tests/` for the bot and shared core,
`backend/tests/` for the API). No extra flags or working directory tricks are
needed.

```bash
# Backend only
pytest backend/tests

# Bot + core only
pytest tests
```

Mobile type checking:

```bash
cd mobile && npx tsc --noEmit
```

---

## 📡 API summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Create account, returns access + refresh tokens |
| `POST` | `/api/auth/login` | Login (rate limited: 5 failures / 15 min) |
| `POST` | `/api/auth/refresh` | Exchange a refresh token for a new pair |
| `POST` | `/api/auth/logout` | Revoke every token issued to the user |
| `GET` | `/api/auth/me` | Current profile |
| `GET/POST` | `/api/transactions` | List / create transactions |
| `PUT/DELETE` | `/api/transactions/{id}` | Update / delete |
| `POST` | `/api/transactions/quick-input` | Parse free text into a preview |
| `POST` | `/api/transactions/quick-input/confirm` | Parse and save |
| `GET` | `/api/reports/{daily,weekly,monthly}` | Period summaries (user timezone) |
| `GET` | `/api/reports/category-breakdown` | Pie-chart data |
| `GET` | `/api/reports/investment` | Allocation by asset and type |
| `GET/POST` | `/api/categories` | List / create categories |
| `GET/POST` | `/api/debts` | List / create debts and receivables |
| `GET` | `/api/debts/summary` | Remaining totals and due-soon count |
| `POST/GET` | `/api/debts/{id}/payments` | Installments |

Dates are ISO `YYYY-MM-DD`. Money is an integer in the smallest currency unit
(rupiah, no decimals).

---

## 🔒 Security notes

- `SECRET_KEY` is mandatory and must be 32+ characters in `ENVIRONMENT=production`.
- Access tokens last 30 minutes; refresh tokens last 30 days. Every token
  carries a `ver` claim matched against `users.token_version`, so logout revokes
  the whole session. The mobile client refreshes transparently and stores tokens
  in SecureStore.
- Login is rate limited per client IP and email; registration and refresh have
  their own per-IP limits.
- CORS origins come from `CORS_ORIGINS`; wildcard origins disable credentials.
- Database files and `.env` files are git-ignored.

---

## 📄 License

Apache License 2.0. See [LICENSE](LICENSE).