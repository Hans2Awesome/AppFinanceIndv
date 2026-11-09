# Transaction editing and change history

Users can select a transaction from Home or Reports, edit its amount, category,
date, note or investment asset, or confirm deletion. The transaction type stays
unchanged. Debt/payment-generated cash rows are read-only here; use the debt
screen to keep balances synchronized.

Every effective edit and successful deletion records an owner-scoped snapshot
with time, action, source and reason. Edits retain before/after values; deletions
retain the previous values with no after snapshot. Saving unchanged fields does
not produce a history entry. History starts when this feature is installed;
changes made before then cannot be reconstructed.

## API contract

All endpoints require the existing bearer authentication. Transaction responses
include `can_edit` and `can_delete`; debt/payment cash rows return `false`.

- `PUT /api/transactions/{id}` accepts `amount`, `category_id`,
  `transaction_date`, `note`, and `asset_name`. Omitted fields remain unchanged.
  Explicit `null` clears category, note, or asset. Amount must be positive and
  date must be valid; neither accepts `null`. Type and audit metadata cannot be
  supplied. A locked derived transaction returns HTTP 409.
- `DELETE /api/transactions/{id}` returns HTTP 204. Missing or foreign-owned
  records return HTTP 404, including repeated deletion.
- `GET /api/transactions/history` returns an array ordered by descending audit
  ID. Optional parameters: `transaction_id`, `limit` (1–200, default 50), and
  `offset` (nonnegative, default 0). A foreign or unknown transaction filter
  returns an empty array, not another owner's history.

Each history entry contains `id`, `transaction_id`, `action`, `source`, `reason`,
`before`, `after`, and `created_at` (UTC ISO 8601). Snapshots contain transaction
type, amount, category ID/name, transaction date, note, asset name, transaction
ID, and internal source key. The app does not display internal source keys.
Sources and reasons are server-controlled. No-op saves create no entry.

## Retention and reporting

Deleted transactions no longer count in balances or reports. Their snapshots
remain available through Change history, including after the original transaction
is gone. There is no restoration feature and no history-edit/delete endpoint.
Permanent account deletion removes that account's history. Linking a bot-only
Telegram account transfers its history with its other data.

Sources distinguish API/app, Telegram and system changes. System entries explain
cash synchronization caused by debt changes or removal of a debt/payment. These
entries do not make the derived cash rows directly editable. Internal identity
merge rewrites are not financial edits and do not create new history entries.

## Safety

The mutation and history write share one transaction. Failure rolls both back.
PostgreSQL locks the transaction row before reading; SQLite acquires a write lock
before the snapshot. Stored category names remain readable even if categories
later change. Reads always filter by the authenticated owner and do not require
the original transaction to exist. History is application-managed, not a
tamper-proof ledger against database administrators or arbitrary direct SQL.

## Verification

Use temporary SQLite and an isolated local PostgreSQL database only. Never point
tests at production. Test editing, clearing notes, unchanged saves, deletion,
history after deletion, ownership isolation, rollback, Telegram linking, debt
cash updates/deletions and permanent account deletion. Physical Android keyboard
and navigation checks require Expo Go/device testing; do not build APKs on this
VPS.

### Android acceptance checklist

Physical-device validation remains separate from automated tests:

1. Tap a Home transaction. Change amount, date, and category, then save. Confirm
   Home and Reports refresh after returning.
2. Clear note and investment asset. Reopen detail and verify they remain empty.
3. Open Change history. Verify before/after values, source, reason, and timezone.
   Save unchanged values and verify no additional history entry appears.
4. Cancel deletion, then confirm deletion. Verify the transaction leaves reports
   while its last snapshot remains accessible through global Change history.
5. Open a debt/payment-generated transaction. Verify direct edit/delete are
   unavailable. Change or remove it through Debt and verify system history.
6. Test offline save/delete and retry. Confirm drafts survive, duplicate taps do
   not submit twice, and failed requests do not show success.
7. With SwiftKey visible, reach every edit field and the save button. Check back
   navigation and history pagination on the target Android device.

### Automated verification

Verified on the feature branch with temporary SQLite files and an isolated
PostgreSQL 16 database, UTF-8 encoding, private Unix socket, and no TCP listener:

- Python suite: 438 passed, 1 skipped. The skip is the PostgreSQL-only row-lock
  case under the SQLite parameter; that case passes under PostgreSQL. SQLite
  locking has its own concurrent-writer regression test.
- Mobile boundary tests: 19 passed, including existing account-security tests.
- TypeScript: `tsc --noEmit` passed after regenerating ignored Expo route types
  with `CI=1 EXPO_NO_DOTENV=1 expo customize tsconfig.json`.
- Ruff and Python bytecode compilation passed. Python wheel packaging passed.
- Reviewer rechecked atomicity, ownership, migrations, mobile race fixes, and the
  Telegram money-suffix regression with no remaining blockers.

The Python suite reports an existing Starlette/httpx deprecation warning. No
APK/native build, production migration, deployment, or physical-device check
was performed.
