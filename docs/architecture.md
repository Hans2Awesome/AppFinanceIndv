# Architecture

## Shape

```
finance_core/            shared, framework-free domain
  db/                    connection, migrations, repositories (users, categories,
                         transactions, debts)
  services/              money/date/category parsing, quick input, transaction save
  reports/               date ranges, aggregation
  timezones.py           user-timezone "today"
  domain.py              TransactionType + labels

backend/app/             FastAPI adapter
  main.py                app factory, startup migrations, CORS
  auth/                  JWT (access/refresh), bcrypt, per-request DB, rate limit
  routes/                auth, transactions, categories, reports, debts
  models/schemas.py      Pydantic request/response models

src/bot04/               Telegram adapter
  bot/                   handlers, keyboards, message formatting
  services/              pending_store, transaction_preview (bot-only)
  config.py, main.py

mobile/                  Expo client
  app/                   routes ((auth), (tabs))
  components/            cards, inputs, debt modals
  services/              axios client, token session, per-resource APIs
```

## Decisions

**One domain layer.** The API and bot previously carried separate copies of
repositories, parsers and reports. They diverged (the bot's `Transaction` had no
category name; the schema owned two different `users` definitions). Both now
import `finance_core`; adapters only translate transport.

**Schema runs once.** `run_migrations` executes at process startup and records
versions in `schema_migrations`. Request handlers never execute DDL. Migration 2
adds `users.token_version` and database triggers that reject non-positive
amounts and unknown `type`/`status` values even when a caller bypasses the
Pydantic schemas. Migration 1 is idempotent, so bot-only databases upgrade in
place. Indexes cover the actual
access paths: `transactions(user_id, transaction_date, id)`,
`transactions(user_id, type, transaction_date, id)`, `categories(user_id, type)`,
`debts(user_id, status)`, `debt_payments(debt_id, payment_date)`.

**Connections are request-scoped.** `get_db` opens one connection per request with
`check_same_thread=False` because FastAPI may run the dependency and endpoint in
different thread-pool threads, and commits on success or rolls back on error.
The bot shares one connection, serializes every DB call behind a lock, runs the
calls with `asyncio.to_thread`, and commits once per handler.

**Repositories do not commit.** Any multi-step write is wrapped in
`finance_core.db.connection.transaction`, so a failure leaves no partial rows
(for example, a user is never created without their default categories).

**User timezone is authoritative.** Report ranges and debt due-soon counts
resolve "today" from `users.timezone` through `finance_core.timezones`. The
server clock never decides a user's date.

**Tokens.** Access tokens are 30 minutes, refresh tokens 30 days, both signed
with `SECRET_KEY` (no default value). The `type` claim prevents using a refresh
token as a bearer credential. Both token types carry `ver`, compared with
`users.token_version` on every use; logout increments the counter and revokes
every session for that user.

**Config lives in the environment.** `finance_core/config.py` is the single
loader for `DATABASE_PATH`, `TIMEZONE`, `CURRENCY`, and `ENVIRONMENT`; the API
and bot add only their own values on top. `EXPO_PUBLIC_API_URL` replaces the
committed tunnel URL, and the quick-start script passes it to Expo instead of
rewriting `mobile/services/api.ts`.

## Known limits

- Tokens are revoked per user, not per device: logging out on one device ends
  all sessions for that account.
- Login, registration, and refresh throttling is in-process. Multi-worker
  deployments need Redis.
- Pending quick-input previews live in bot process memory; a restart drops them
  after the 10-minute TTL window.
- Reports aggregate in Python over the requested date range. Fine for personal
  data volumes; move to SQL `SUM ... GROUP BY` if ranges grow large.
- SQLite with WAL supports the single-instance deployment model only.