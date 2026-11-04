# 💰 AppFinanceIndv — Personal Finance Management System

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

One repository, three clients, one domain layer:

- **Mobile app** — Expo + React Native + TypeScript
- **REST API** — FastAPI + Pydantic + PostgreSQL (SQLite for local dev)
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
| Database | PostgreSQL on Supabase; SQLite fallback when `DATABASE_URL` is empty |
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

### 3. Supabase (production database)

Optional. Skip this step to keep using the local SQLite file.

1. Create a project at supabase.com.
2. Open **Project Settings > Database > Connection string > URI** and copy it.
3. Put the **transaction pooler** URI (port `6543`) in the root `.env` and in
   `backend/.env` as `DATABASE_URL`. Keep `?sslmode=require` at the end, and
   URL-encode the password.
4. Create the schema and copy the existing data with the **direct/session**
   URI (port `5432`), not the pooler URI. DDL and the data copy must run in one
   session:

```bash
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite bot04.sqlite3 \
  --database-url "postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres"
```

The script builds the schema, copies `users`, `categories`, `transactions`,
`debts`, `debt_payments` and `recurring_transactions` with their original ids,
resets the id sequences, and verifies every row count. It never writes back to
SQLite and is safe to re-run: ids that already exist are skipped.

5. Restart the API first, then the bot. Both read `DATABASE_URL`, so they share
   one database. `docs/deploy-supabase.md` has the full go-live order and the
   rollback steps. To move an existing PostgreSQL database to another Supabase
   project (for example after changing region), use
   `docs/pindah-database-supabase.md` and `scripts/copy_postgres_database.sh`.

Notes:

- Use the transaction pooler (port `6543`). The driver disables prepared
  statements because the pooler cannot keep them.
- `DATABASE_PATH` stays as the fallback for tests and offline development.
- The recurring scheduler still runs inside the API process, so the API must be
  running for recurring transactions to be materialized.

### 4. Mobile app

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

### 5. Telegram bot (optional)

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

Link a Telegram account to a mobile account: request a code in the app
(Settings), then send `/link <code>` to the bot. Only the newest code per user
is valid. Send `/unlink` to detach Telegram again; the financial data stays.
A bot-only account (no email) cannot unlink, because it has no mobile account.

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

# PostgreSQL portability (real server required, skipped when unset)
POSTGRES_TEST_URL="postgresql://user:pass@127.0.0.1:5432/finance_test" \
  pytest tests/test_postgres_portability.py
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
| `POST` | `/api/auth/telegram-link-token` | Issue a 6-digit code for `/link` in the bot |
| `DELETE` | `/api/auth/telegram-link` | Unlink Telegram, keeping all financial data |
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

Cash transactions generated from a debt or an installment carry a `source_key`
and are read-only through `/api/transactions`: `PUT` and `DELETE` return `409`.
Change or remove them through the debt endpoints, so the ledger and the debt
balance stay in sync. Deleting a debt deletes its generated cash rows too.

---

## 🔒 Security notes

- `SECRET_KEY` is mandatory and must be 32+ characters in `ENVIRONMENT=production`.
- `ENVIRONMENT=production` refuses to start when `DATABASE_URL` is empty, so a
  misconfigured VPS can never keep writing to the local SQLite file. The check
  lives in `finance_core`, so the API and the Telegram bot both fail loudly.
- Access tokens last 30 minutes; refresh tokens last 30 days. Every token
  carries a `ver` claim matched against `users.token_version`, so logout revokes
  the whole session. The mobile client refreshes transparently and stores tokens
  in SecureStore.
- Login is rate limited per client IP and email; registration and refresh have
  their own per-IP limits.
- CORS origins come from `CORS_ORIGINS`; wildcard origins disable credentials.
  In `ENVIRONMENT=production` a wildcard is refused at startup, because the
  Android app and the bot are not browsers and never need one.
- `/docs`, `/redoc` and `/openapi.json` are disabled in `ENVIRONMENT=production`,
  so scanners behind the Cloudflare Tunnel cannot read the API schema.
- The Supabase tables have RLS enabled with no policy, so the Data API exposes
  nothing through the `anon` role. The API and bot connect as `postgres`, which
  has `BYPASSRLS`, so their queries are unaffected.
- Login throttling keys on the real client IP. `CF-Connecting-IP` and
  `X-Forwarded-For` are honored only from addresses in `TRUSTED_PROXIES`
  (localhost by default), so a direct client cannot spoof its address. Run
  Uvicorn with `--proxy-headers --forwarded-allow-ips="127.0.0.1"` behind the
  tunnel; `scripts/run_app.py` already does this.
- `DATABASE_URL` contains the Supabase password. Keep it in `.env` only; never
  commit it or ship it in the mobile bundle. Mobile and bot talk to the API, not
  to the database.
- Database files and `.env` files are git-ignored.

---

## 📄 License

Apache License 2.0. See [LICENSE](LICENSE).