# Device-local app lock

Open **Account > Settings > Kunci aplikasi** to create and confirm a six-digit
PIN. Strong enrolled OS biometrics can be enabled afterward using the current
PIN and a successful native biometric prompt. PIN remains the fallback when
biometrics are unavailable or cancelled. This setting affects this installation
only; it does not change the account password or other devices.

## Behavior

- Cold launch and background transitions lock authenticated financial screens.
  Inactive transitions cover content; a native biometric prompt can continue
  through its own inactive event, but not through a background event.
- Change PIN, disable lock, and biometric preference changes require the
  current PIN. Five incorrect PINs impose a persisted 30-second cooldown.
- **Lupa PIN** signs out locally. A successful fresh password/Google sign-in
  clears the previous device lock. Enable a new PIN afterward. Token refresh and
  password changes do not silently remove the lock.
- Web does not support this native device-lock feature. Missing biometric native
  support leaves PIN available. Missing secure crypto prevents setup rather than
  storing a weak or plaintext fallback.

## Security boundary

SecureStore holds a versioned verifier, 256-bit random secret, biometric
preference, failed-attempt count, and retry timestamp. The verifier is SHA-256
over a domain-separated secret and PIN. The PIN itself is never persisted,
logged, or sent to the API. The OS-encrypted SecureStore, not a short PIN hash
alone, protects the record. This is a local privacy gate, not encrypted financial
storage or protection against rooted devices or malicious runtime modification.

Storage read/write failures and malformed records fail closed. The lock screen
offers storage retry or sign-out recovery. Settings writes and unlock proofs
cannot open the gate after session/background invalidation. Session persistence
is serialized so an in-flight refresh cannot restore tokens after logout.
Disabling first writes a durable pending backup. Interrupted deletion recovers
the enabled record, and successful rollback removes that backup before later
settings changes can proceed.

Opaque root and existing-sheet covers prevent interaction and accessibility
traversal of financial content while locked. Android back cannot dismiss the
gate. Existing native sheets render the gate inside their own modal instead of
presenting a competing native modal. Native screenshot prevention also protects
Android recent-app previews when the installed module supports it. Native/OS
capture guarantees still require device testing.
Financial confirmations use in-tree dialogs rather than native alerts that can
remain above a privacy cover. Background/session invalidation dismisses these
dialogs and rejects their stale action callbacks.

## Native availability

Dependencies match Expo SDK 58: `expo-local-authentication`, `expo-crypto`, and
`expo-screen-capture`. The local-authentication config plugin supplies the iOS
Face ID usage description. Existing installed custom binaries do not gain new
native modules from a JavaScript update. Rebuild on the normal external build
machine to test all features; do not build APKs on this VPS.

## Device acceptance checklist

1. Set a PIN through Account settings. Verify mismatch/invalid length rejection,
   then background and reopen. Try Android back and a transaction deep link.
2. Enter five wrong PINs. Kill/reopen the app and verify the cooldown persists.
   Enter the correct PIN afterward and verify protected screens resume.
3. Enroll a fingerprint in Android settings. Enable biometrics with PIN and
   native proof. Test success, cancellation, unavailable sensor, and PIN fallback.
4. Open a Debt sheet or Google-link sheet, background, and return. Verify no
   financial fields can be seen, tapped, or read by accessibility before unlock.
   Check Android recent apps and screenshots. Test iOS separately if supported.
5. Change/disable PIN with correct and incorrect current PIN. Test Forgot PIN,
   sign-in recovery, and logout during an in-flight token refresh. With SwiftKey
   open, verify every PIN field and action remains reachable.

No backend migration or production database access is required for this feature.

## Automated verification

- Mobile tests: 60 passed (41 app-lock cases plus existing security/history tests).
- TypeScript: `tsc --noEmit` passed after ignored Expo route-type regeneration.
- Expo public configuration resolved successfully with dotenv disabled.
- Android JavaScript/Hermes export passed with two Metro workers and a dummy API
  URL. This is a bundle check, not an APK/native build or device test.
- Python regression suite: 414 passed, 9 skipped without a PostgreSQL test URL.
  No Python/backend behavior changed. Ruff passed; the suite still reports its
  existing Starlette/httpx deprecation warning.
- Security review findings were fixed and rechecked, including stale token
  writes, cancelled disable recovery, stale pending-marker cleanup, and protected
  confirmation dialogs. Final inspected paths have no remaining blockers.

Fingerprint sensor behavior, OS screenshots, recent-app previews, native-sheet
layering, and keyboard navigation still require physical-device acceptance.
