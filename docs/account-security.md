# Account security

## Enable password recovery

Set these values in the backend's private environment, not the mobile app or Git:

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=your-mail-provider-username
SMTP_PASSWORD=your-mail-provider-app-password
SMTP_FROM=Finance App <noreply@example.com>
```

Use a sender your provider authorizes. Port 465 requires `SMTP_SECURITY=ssl`.
Only certificate-verified TLS is supported. Username and password must be supplied
together if authentication is required. No new Python dependencies are needed.
Restart the backend after configuring delivery.

Without valid host/from/security settings, recovery requests return HTTP 503 for
every email. There is no development bypass, printed code, or API-returned code.
The Google sign-in and ordinary password flows remain available without SMTP.

Recovery emails include a responsive HTML layout matching the app's paper-and-ink
design and an equivalent plain-text alternative. The code remains selectable text;
no remote images, web fonts, tracking resources, or app links are required. The
hidden preheader does not include the code. Email-client rendering and inbox
previews can vary; check the actual message on the devices your users use.

Verify delivery with a disposable password account and a mailbox you control.
Request recovery in the app, check the inbox/spam folder, enter the six-digit
code in the same recovery screen, and sign in with the new password. SMTP errors
produce a generic response and invalidate the undelivered request; server logs
contain only a generic delivery-failure message. A response alone is not proof
that an email reached its destination.

## API reference

| Endpoint | Body | Success |
|----------|------|---------|
| `POST /api/auth/change-password` | `current_password`, `new_password` | New access/refresh pair and user |
| `POST /api/auth/forgot-password` | `email` | `message`, opaque `request_id`, `expires_in: 600` |
| `POST /api/auth/reset-password` | `request_id`, six-digit `code`, `new_password` | Message; sign in again |
| `DELETE /api/auth/account` | `confirmation: "DELETE"`, `password` or `id_token` | HTTP 204, empty body |

Password changes and deletion require the normal bearer access token. New
passwords require at least eight characters and at most 72 UTF-8 bytes. A password
change verifies the old password, rejects reuse, revokes all older access/refresh
tokens, and returns a replacement session for the current device. Recovery also
revokes all sessions but never automatically logs the caller in.

Recovery requests have the same response for unknown emails and Google-only
accounts. Only password accounts receive email. Google-only users must sign in
through Google and manage their Google password there. Each recovery request
expires after ten minutes and permits at most five guesses. Resending invalidates
the previous request. Codes are stored as secret-keyed HMAC digests, not plaintext.
Changing or resetting a password invalidates pending recovery requests.

Throttle windows are 15 minutes: recovery requests allow ten per IP and three per
email; code confirmation allows 30 per IP; password-change/deletion actions share
five per IP/account. These process-local counters reset on restart. Challenge
guess budgets are persisted in the database and survive restarts. Multi-worker
deployments need a shared rate limiter before relying on aggregate IP limits.

## Permanent account deletion

The app requires a permanent-deletion acknowledgement and typing `DELETE`.
Password accounts must enter their password even if Google is linked. Google-only
accounts must obtain another Google ID token whose subject matches the stored
identity. The token must have an issuance timestamp within five minutes, with at
most 60 seconds of future clock drift. This path requires an Android build with
native Google sign-in, not Expo Go.

Deletion removes the live user row and cascades categories, transactions, debts,
debt payments, recurring schedules, Telegram link codes, and recovery challenges.
It disconnects application identities; it does not delete the external Google or
Telegram account. Old application tokens stop working. Other users remain intact.
Historical backups are not rewritten by the endpoint and follow operator
retention policy. Export any needed records before deletion.

## Verification

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
cd mobile
npm run test:security
./node_modules/.bin/tsc --noEmit
```

Tests use temporary SQLite databases and mocked SMTP/Google verification. They
must never point to a production database. Live SMTP delivery, real Google
reverification, and physical Android keyboard/navigation behavior need separate
device checks. Build an updated APK through EAS cloud only when requested.

## Integration verification

Integrated with the Google authentication and Android keyboard fixes on local
`main` on 2026-11-09. The login conflict preserves the shared `Screen` component's
`keyboardBehavior="padding"` override and adds the recovery link without restoring
the redundant keyboard-avoidance wrapper. Other keyboard components and the
missing-Google-client-ID guard remain unchanged.

Verification on the combined tree:

- Python suite: 391 passed, no skips, using an isolated local PostgreSQL database
  alongside the temporary SQLite fixtures. All test schemas were removed and the
  PostgreSQL cluster was stopped afterward.
- Ruff, Python compilation, and mobile TypeScript checks passed. Expo's generated
  route declarations were refreshed to include the three new account screens.
- Seven mobile security tests and three login merge structure assertions passed.
- Follow-up review found redundant keyboard-avoidance wrappers in the three new
  account screens. Each now delegates to `Screen` with `keyboardBehavior="padding"`.
  Three regression tests failed before the fix and passed afterward; the mobile
  security suite now has ten passing tests. TypeScript and Android export were
  rechecked after this fix. Physical-device keyboard behavior remains unverified.
- Android JavaScript/Hermes export passed with two Metro workers. This is not an
  APK build or physical-device verification.

No deployment, production database migration, live recovery request, or APK build
was performed during integration. Recovery, password change, account deletion,
and native Google authentication still require verification on the target device
against the updated backend before release.
