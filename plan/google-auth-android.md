# Implementation Plan: Google Authentication for Android

## Objective

Add native Google registration/sign-in to the Android app while preserving the existing FastAPI JWT sessions, password login, Telegram linking, and financial data ownership. Existing accounts must explicitly link Google after authenticating with their password. Never automatically link accounts by matching email.

**Status:** Implementation on `feature/google-auth-android` is partially complete. Native compatibility and a user-owned feature specification remain release blockers.
**Branch:** `feature/google-auth-android`
**Architecture:** Android obtains a Google ID token. FastAPI verifies it, resolves an immutable Google subject to the existing application user, and returns the current `TokenResponse`. The app stores only first-party session tokens through its existing session service.
**Stack:** Python 3.11+, FastAPI/Pydantic v2, SQLite and psycopg/PostgreSQL, Expo SDK 58, React Native 0.88, React 19.3, TypeScript 6, Yarn, Expo Router.

### Execution status (2026-11-07)

Done:
- Android native setup: `react-native-nitro-google-signin@2.3.1`, `react-native-nitro-modules@0.37.2`, `expo-dev-client@58.0.18`, config plugin, EAS `development` APK profile.
- `expo prebuild --platform android` passed; Gradle compiled app Java/Kotlin and the Nitro/Google modules before the local build was stopped at the user's request. No APK was produced on this server.
- Schema v6 in both dialects, user repository helpers, verifier, both endpoints, rate limits, mobile service/UI, docs.
- `ruff check .` passes; `302` tests pass and `6` PostgreSQL portability tests skip without a local server; mobile `tsc --noEmit`, `expo config --type prebuild`, and the bundled compatibility validator exit 0.
- Mobile duplicate-submit guard now covers the password and Google flows together; link requests require the password field.

Blocked or pending (user-executed):
- `docs/google-auth-android.md` feature specification still does not exist.
- Google Cloud Web/Android OAuth clients and all signing SHA-1 values are not configured.
- APK build is moved to expo.dev by user request; EAS/device smoke test, Play App Signing fingerprint, and production rollout remain user-executed.
- The package's bundled compatibility validator is a false positive (its `2.0.x` key does not match `2.3.1`, so it skips checking RN 0.88). The main-branch matrix only lists RN through 0.87. A real EAS build is the only proof.
- The `iosUrlScheme` in `mobile/app.json` is an Android-only placeholder; replace it before any iOS build.

## Scope

Included:
- Google sign-in and first-time account creation on Android, exposed from login and registration screens.
- Explicit Google linking in Settings for existing password accounts, with password reauthentication and matching verified email.
- Additive schema migration, token validation, throttling, collision handling, automated backend tests, and Android device verification.
- Google Cloud OAuth setup guidance and APK/development-build configuration.

Excluded:
- iOS/web Google authentication, browser redirects, Firebase Auth, Supabase Auth, and replacing existing JWT/session storage.
- Automatic email linking, merging two mobile accounts, switching a linked Google identity, Google unlinking, adding a password to a Google-only account, and account recovery.
- Google API access, offline access, Google access/refresh token storage, or requesting Calendar/Drive permissions.
- Unrelated architecture, dependency, rate-limiter, or scheduler refactors.

## Context

### User-approved requirements

1. Android is the only new Google authentication target.
2. Native APK/development builds are acceptable. Google authentication does not need to work in Expo Go.
3. Existing password accounts must log in before explicitly linking Google. Do not auto-link by email.
4. Google Cloud project and OAuth clients do not exist yet.

### Read existing documentation first

`PRODUCT.md`, `DESIGN.md`, `README.md`, `docs/architecture.md`, and `docs/mobile-quickstart.md` exist. `PRODUCT.md:27` currently requires Expo Go; the approved native build exception must be documented. `DESIGN.md` defines the ledger visual system and accessibility floor. Existing user-facing copy is Indonesian; retain the current app's localization conventions.

A feature PRD/TDD/API/ADR for Google authentication is missing. The planner requested that the user create `docs/google-auth-android.md`. Do not create that missing specification on the user's behalf. Before implementation, require it to confirm the requirements and contracts below. If supplied elsewhere, read that artifact and reconcile differences first.

### Repository evidence

| Area | Evidence and implication |
| --- | --- |
| Token issuance | `backend/app/routes/auth.py:51-58` defines `_build_token_response`; reuse it for Google authentication. |
| Password sign-in | `backend/app/routes/auth.py:96-123` rejects absent password hashes already. Google-only accounts can keep `password_hash = NULL`. |
| User persistence | `finance_core/db/users.py:13-60` maps `AppUser`; `_USER_COLUMNS` is explicit. Extend mapping without exposing the Google subject in public responses. |
| Default categories | `finance_core/db/users.py:97-123` creates a password user and seeds categories. Preserve atomic default-category creation for Google registration. |
| Transaction traps | `finance_core/db/connection.py:363-383` commits SQLite blocks instead of implementing nested savepoints. Avoid nested helper contexts in the new Google registration path. |
| Telegram merge | `finance_core/db/users.py:289-431` merges bot-only users; identity checks must never classify a Google identity as a disposable bot-only account. |
| Migrations | `finance_core/db/migrations.py` and `postgres_schema.py` are at version 5. Add version 6; never rewrite versions 1-5. |
| Copy tooling | `scripts/migrate_sqlite_to_postgres.py:28-43` explicitly lists user columns. Include the new identity column or migrations silently lose Google access. |
| Mobile sessions | `mobile/services/auth.ts:17-20` persists the existing `AuthResponse`; `session.ts` owns SecureStore. Reuse these rather than inventing another session store. |
| Android identity | `mobile/app.json:9-11` uses `com.financeapp.mobile`; preserve this package and the existing EAS project. |
| Build profiles | `mobile/eas.json` has preview APK and production AAB profiles, no development profile. |

No `graphify-out/graph.json` exists. Evidence above comes from direct source reads. Do not extract a graph without asking the user first.

### Alternatives and decisions

| Choice | Benefit | Cost / trap | Decision |
| --- | --- | --- | --- |
| Native Android Credential Manager | Current Android integration, native chooser, avoids deprecated Android Google Sign-In SDK | Native rebuild and dependency compatibility must be proven | Preferred, gated on a build spike |
| Free original `@react-native-google-signin/google-signin` | Established package, smaller integration | Original Android SDK is deprecated; modern Credential Manager belongs to its paid offering | Do not silently select this fallback |
| Paid Credential Manager offering | Mature supported native option | Requires explicit budget/license approval | Ask user only if preferred package fails |
| Browser OAuth | Avoids some native SDK integration | Redirect and deep-link work, different Android UX, Expo Go is no longer a requirement | Rejected for this scope |
| Firebase/Supabase Auth migration | Managed identity lifecycle | Replaces current session/ownership system and expands scope | Rejected |
| Nullable unique `users.google_sub` | Small additive schema, matches Telegram identity storage | Supports only one Google identity per user | Selected; no generic provider table yet |
| Explicit linking | Proves ownership of old account and Google account | Extra password step | Selected by user |

**Important compatibility evidence:** Expo's current Google guide lists `react-native-nitro-google-signin` as a Credential Manager option. Registry metadata reports version 2.3.1, but the published compatibility page and repository `compatibility.json` only list React Native through 0.87. This app declares 0.88. Do not assume compatibility based on broad peer dependencies. The package's no-Firebase Expo plugin also validates an iOS URL scheme even for Android-oriented setup. These are explicit spike questions, not permission to add fake iOS configuration, downgrade Expo/RN, patch validators, or introduce Firebase.

**Risk assessment:** HIGH because this changes authentication, identity uniqueness, a public API, and both database schemas. Jev verify was attempted on 2026-11-07 and returned HTTP 404. Tier: HIGH by domain. `proceed`, `spec_fit`, and `needs_human`: unavailable, no scores inferred. Manual decision: proceed with planning; require prerequisites, security review, local PostgreSQL verification, and device acceptance before release.

## Dependencies

1. User-created `docs/google-auth-android.md` accepting the scope, endpoint behavior, and MVP exclusions.
2. User-controlled Google Cloud project, branding/audience/consent settings, and approved test users when the OAuth app is in testing.
3. One Web OAuth client ID for backend audience and Android configuration. Create Android OAuth clients for package `com.financeapp.mobile` and each actual signing SHA-1: local debug if used, EAS APK signing certificate, and Play App Signing certificate before Play distribution. Client IDs must belong to the same Google project.
4. An Android physical device with supported Google Play Services, EAS build access or a local Android toolchain, and local PostgreSQL for portability/race tests. SHA-1 fingerprints and client IDs are public configuration; signing keys and OAuth client secrets must never be pasted into chat or committed.
5. Native package compatibility proved by Step 2. Backend verification uses `google-auth[requests]` plus `CacheControl` for certificate caching, added only to backend requirements. No Google client secret is required for ID-token verification.

## Files / Areas Likely Affected

| Files | Responsibility |
| --- | --- |
| `finance_core/db/migrations.py`, `finance_core/db/postgres_schema.py` | Add schema version 6 and unique Google subject index. |
| `finance_core/db/users.py` | Google identity lookup/create/link and `google_linked`; preserve Telegram safety. |
| `scripts/migrate_sqlite_to_postgres.py` | Preserve `google_sub` during database copies. |
| `backend/app/auth/google.py` (new) | Verify Google tokens and expose a typed verified identity with sanitized exceptions. |
| `backend/app/config.py`, `backend/.env.example` | Optional `GOOGLE_WEB_CLIENT_ID`, read only from backend configuration. |
| `backend/app/routes/auth.py`, `backend/app/models/schemas.py`, `backend/app/auth/rate_limit.py`, `backend/requirements.txt` | Exchange/link contracts, rate limits, response field, dependencies. |
| `mobile/services/googleAuth.android.ts`, `mobile/services/googleAuth.ts` (new) | Native-only token acquisition and unsupported-platform fallback; no native module evaluation in web/iOS/Expo Go. |
| `mobile/services/auth.ts`, `mobile/types/index.ts` | Exchange/link methods and Google-link state using current sessions. |
| `mobile/components/auth/GoogleAuthButton.android.tsx`, `mobile/components/auth/GoogleAuthButton.tsx` (new) | Branded accessible Android control and a safe hidden fallback. |
| `mobile/app/(auth)/login.tsx`, `register.tsx`, `mobile/app/(tabs)/settings.tsx` | Native Google entry points and password-confirmed link flow. |
| `mobile/package.json`, `mobile/yarn.lock`, `mobile/eas.json`, `mobile/app.json` or `mobile/app.config.ts`, `mobile/.env.example` | Native setup, development build, public client ID. Preserve existing config. |
| `tests/test_google_users.py` (new), `tests/test_migrations.py`, `tests/test_schema.py`, `tests/test_users_repository.py`, `tests/test_postgres_portability.py` | Migration, persistence, concurrency and Telegram regressions. |
| `backend/tests/test_google_verifier.py`, `backend/tests/test_api_google_auth.py` (new), `backend/tests/test_api_auth.py`, `tests/test_config.py` | Verification/security/API/config regression tests. |
| `PRODUCT.md`, `README.md`, `docs/architecture.md`, `docs/mobile-quickstart.md` | Update existing documentation only, after user specification exists. |

## API and Identity Contracts

### Configuration and verification

- `GOOGLE_WEB_CLIENT_ID` on backend must exactly match `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` in the Android build. The expected audience is never supplied by the request. Android client IDs are not the backend audience.
- With backend client ID absent, keep password/bot startup functional and return sanitized 503 from Google endpoints. With mobile client ID absent, hide Google controls without throwing at module import.
- Verify using `google.oauth2.id_token.verify_oauth2_token` with explicit audience, then require issuer `accounts.google.com` or `https://accounts.google.com`, nonempty string `sub`, valid email, and `email_verified is True`. Enforce subject maximum 255 and email maximum 320 characters. Do not trust client profile fields or use `tokeninfo` in production.
- Fetch Google certificates with a fixed 5-second network timeout and cache respecting HTTP freshness, using a thread-local cached Requests transport if needed for sync endpoint threads. Never accept invalid tokens when keys cannot be retrieved. Distinguish validation failure (401) from provider/transport unavailability (503). Never log request bodies, ID tokens, passwords, or full Google verification exceptions.
- Request only identity/email/profile. `offlineAccess` stays false. Google tokens exist only transiently; SecureStore persists first-party JWTs only.
- No server-issued nonce/challenge in this ID-token-exchange MVP. ID tokens are bearer credentials replayable until expiry if stolen. Require HTTPS, never log them, no automatic native session restoration, and document this residual risk. Do not pretend expiry alone makes them single-use.

### Endpoints

| Endpoint | Request | Success | Failure |
| --- | --- | --- | --- |
| `POST /api/auth/google` | `id_token`: nonempty string, maximum 16384 characters | 200 current `TokenResponse` for both new/existing Google users | 401 invalid token; 409 email belongs to an unlinked account; 429 throttled; 503 disabled/unavailable |
| `POST /api/auth/google/link` | Bearer JWT plus `id_token` and `password` (same byte/length limits as existing login) | 200 `UserResponse` with `google_linked: true` | 401 invalid session/password/token; 409 email mismatch, subject already owned, or replacement attempted; 429 throttled; 503 unavailable |

`UserResponse` gains `google_linked: bool = False` and `has_password: bool`; never return `google_sub`. The second field lets Settings distinguish a Google-only account, which has no password to confirm. Keep all existing `TokenResponse` fields, refresh behavior and `ver` semantics unchanged. Human-readable string `detail` messages must remain compatible with `describeApiError`; do not add a new incompatible error envelope.

### Resolution rules

1. Look up Google login by verified `sub` first. Existing identity signs into the same `users.id`, even if the provider email subsequently changes. Do not overwrite stored account email/name/timezone or financial data during login.
2. For unknown `sub`, normalize the verified email and reject existing-email collisions with 409 and guidance to password-login and link in Settings. Do not issue tokens or create another user. For a genuinely new identity, create user with NULL password and seed default categories atomically using default timezone/currency.
3. Linking requires a valid current session, correct current password, verified Google email equal to stored normalized email, no existing different subject, and no other user's claim on that subject. Repeated same-subject linking is idempotent after reauthentication. Do not allow authenticated clients to submit a target `user_id`.
4. Enforce subject ownership with a database unique index and conditional update, not a check-then-write alone. On uniqueness races, roll back before re-reading. Re-read successful same-subject registration races and return that identity; other collisions become 409 without partial users/categories. Do not catch a PostgreSQL exception and continue using its aborted transaction.
5. Subject linking changes no application user IDs or financial ownership. No token-version increment is needed because linking adds a login method without revoking existing sessions. Existing logout still increments token version. Telegram merge/unlink must work for Google-created mobile users and never delete a user owning a Google identity.

## Implementation Steps

### Step 1: Resolve external and specification prerequisites
**Owner: builder inline, user supplies cloud configuration and specification.**

- [ ] Read the user-created feature specification and existing project docs. If absent, stop code implementation and ask for it; planning alone is not its replacement.
- [ ] Guide the user through Google Cloud Web and Android OAuth client creation. Record package, build variant, client-ID role and signing-fingerprint mapping without collecting secrets.
- [ ] Confirm APK-first testing versus Play distribution. Play-signing OAuth registration can wait for Play distribution but must be listed as a release gate.
- [ ] Freeze the API/identity contracts above for tester and designer. Any spec conflict returns to the user before implementation.

Verification: written prerequisite checklist and user confirmation; no production database or credentials are modified.

### Step 2: Prove native compatibility before domain changes
**Owner: builder inline.**

- [ ] Inspect the current published package's compatibility metadata and Expo plugin source against actual installed Expo/RN versions. Candidate is `react-native-nitro-google-signin` 2.3.1 with a matching Nitro Modules release; do not claim RN 0.88 support without evidence.
- [ ] In a disposable spike worktree, test a genuine Android-only Google Cloud setup with explicit Web client ID, no Firebase and no fabricated iOS URL scheme. The known plugin validation issue must have a documented supported solution, not an ad hoc plugin fork.
- [ ] Use Yarn and Expo's version resolver for Expo packages. Builder alone owns dependency/config/lockfile edits. Add an EAS development profile (`developmentClient: true`, internal distribution) only when using a development client. Preserve preview APK, production AAB, API URL, package, scheme and EAS project ID.
- [ ] Run compatibility validation, Expo config/prebuild for Android, a native compile, and physical-device token acquisition. Native artifacts stay generated/ignored. A Metro reload or successful TypeScript check is not native-build evidence.
- [ ] If supported setup/build cannot be demonstrated, stop and ask the user to select a supported paid Credential Manager option or wait for RN 0.88 support. Do not silently downgrade Expo/RN, adopt legacy GSI, add Firebase, or bypass compatibility validation. Commit only a verified spike outcome to the feature branch, not temporary debug UI.

Verification: record exact dependency versions, Android plugin setup, build command/result and real device result. This gate blocks all later implementation, not just release.

### Step 3: Add identity persistence and migration tests
**Owner: builder inline.**

- [ ] Write failing tests in `tests/test_google_users.py` for fresh migration, v5 upgrade, idempotent v6, multiple NULL subjects, duplicate non-NULL rejection, mapping and default-category rollback. Update hardcoded version assertions using one bounded mechanical script across affected tests, not delegated per file.
- [ ] Add v6 nullable `google_sub TEXT` and unique non-NULL subject index in both dialects. Validate nonempty/max-length subjects in the repository; preserve all v1-v5 migrations and existing RLS/advisory locks. No new table means no new RLS policy.
- [ ] Add `AppUser.google_sub` and `google_linked`, update explicit select/mapping lists, and introduce focused `get_user_by_google_sub`, `create_google_user`, and `link_google_identity` functions. New helpers leave commit/rollback to one outer operation; do not call the existing nested-transaction user creation helper from the new path.
- [ ] Capture the inserted user ID immediately before seeding categories: PostgreSQL's lazy `lastrowid` wraps connection-level `lastval()`, which subsequent category inserts change. Prefer `INSERT ... RETURNING id` where appropriate or immediate `lastrowid` access before any other INSERT. Test that token user ID and category owner remain correct when sequences differ.
- [ ] Protect Telegram merge eligibility with an explicit Google identity check in addition to existing email/password checks. Confirm Google-only mobile users can link/unlink Telegram without losing their Google account or financial data.
- [ ] Extend SQLite-to-PostgreSQL user copying to include `google_sub`; old source databases without that column remain copyable. Add round-trip coverage.

Verification: `pytest tests/test_google_users.py tests/test_migrations.py tests/test_schema.py tests/test_users_repository.py` plus copy/portability coverage on local PostgreSQL. Commit green persistence tests before endpoint work.

### Step 4: Implement verification, configuration and endpoints
**Owner: builder inline, parallel batch A with Step 5. Depends on Steps 1-3.**

- [ ] Add backend-only Google verification dependencies and optional client-ID configuration. Add a typed `VerifiedGoogleIdentity` and sanitized invalid/unavailable exceptions in `backend/app/auth/google.py`, with a narrow `verify_google_id_token(token)` seam for tests.
- [ ] Verify signature/audience/issuer/expiry using official Google auth, strictly validate verified email and subject claims, enforce bounded cached certificate transport, and distinguish 401/503. Tests must not contact Google.
- [ ] Add schemas and the two endpoints exactly as contracted. Reuse `_build_token_response`, existing current-user dependency and password verifier. Normalize email before lookup; identity reads precede any mutation.
- [ ] Add distinct pre-verification per-IP throttles: 10 exchange attempts / 15 minutes and 5 link attempts / 15 minutes, including failed attempts. Return `Retry-After: 900`; do not alter existing limiters. Keep in-process deployment limitation explicit.
- [ ] Implement portable uniqueness handling and whole-operation rollback for first registration and linking races. Catch only actual uniqueness conditions, not every database error. Preserve current password response/refresh/logout behavior and never accept Google tokens directly as API bearer credentials.

Verification: new verifier/API tests from Step 5, existing auth/security tests, and `ruff check .`. Review diff for credential exposure and scope creep, then commit.

### Step 5: Add isolated backend security and concurrency tests
**Owner: tester subagent, parallel batch A with Step 4.**

Files owned exclusively by tester: new `backend/tests/test_google_verifier.py`, new `backend/tests/test_api_google_auth.py`. Builder owns shared fixtures/config and existing tests. Tester reports needed fixture changes rather than editing them.

- [ ] Write against the frozen endpoint contracts and verifier seam. Cover first sign-in, repeat sign-in, same user/category count, normalized email, unchanged identity on provider email change, existing-email 409, linked/password sign-in, refresh and global logout, and response privacy.
- [ ] Exercise invalid signature, expired token, wrong issuer/audience, missing/empty subject, false/string/missing `email_verified`, bad email, oversized body fields, certificate outage, disabled configuration and rate-limit-before-verification. Mock only transport/Google boundary, not the route's ownership decisions. Include verifier delegation argument assertions and signed-token rejection tests where appropriate.
- [ ] Cover link without session, bad password, wrong email, subject claimed by another account, replacement attempt, repeated idempotent link, no token issuance on conflict, no partial categories, and transactional rollback.
- [ ] Add simultaneous signup/link scenarios through independent connections using existing local PostgreSQL patterns, coordinated with builder-owned portability coverage. Do not touch shared production or Supabase data. Correct outcomes must include zero 500s and no ownership reassignment.

Verification: tests fail for the intended missing behavior initially and pass after Step 4. Report exact commands, counts and any skipped local PostgreSQL coverage. No production credentials or live Google network in tests.

### Step 6: Add Android service and app API methods
**Owner: builder inline. Depends on Steps 4-5.**

- [ ] Extend `User` with `google_linked`, add `authApi.googleLogin({id_token})` saving the current `AuthResponse`, and `authApi.linkGoogle({id_token,password})` returning updated `User`. Do not store password or provider token.
- [ ] Implement platform-resolved native token acquisition, availability and sign-out. Guard Expo Go/missing native module before importing/evaluating Nitro. Non-Android fallback never imports native code. Missing mobile client ID disables Google, not password auth.
- [ ] Configure explicit Web client ID, no extra scopes/offline access/auto-select. Acquire credentials only after user action, handle cancellation as a normal return, handle missing Play Services and OAuth misconfiguration separately, and reject empty ID token before HTTP exchange.
- [ ] Extend logout with best-effort native Google sign-out after server logout. Native failure must never prevent first-party `clearSession()` or navigation. Logout does not revoke Google consent or unlink the identity.
- [ ] Freeze the service interface for UI: `isGoogleAuthAvailable(): boolean`, `requestGoogleIdToken(): Promise<string | null>` (NULL is cancellation), `signOutGoogle(): Promise<void>`. UI uses auth API methods rather than calling endpoints directly.

Verification: `cd mobile && npx tsc --noEmit`; verify password login/register and module imports on Android native plus web/iOS fallback and Expo Go do not crash. Native compatibility evidence remains required from Step 2.

### Step 7: Add login, registration and Settings UI
**Owner: designer subagent, parallel batch B with Step 8. Depends on Step 6.**

Designer owns auth screens, Settings, and new `components/auth/GoogleAuthButton*` only. No dependency, lockfile, backend, type or service edits.

- [ ] Add a Google-branded native control on Android login and registration screens with an explanatory separator. Use the verified package's branded native button in manual (`signInBehavior="none"`) mode so Step 6 owns orchestration. Keep Google branding intact and the surrounding ledger design unchanged.
- [ ] Disable password and Google actions during either authentication operation, prevent double submissions, expose busy/disabled accessibility state and keep touch targets at least 44x44. Navigate only after backend success and `saveSession` completion.
- [ ] Surface email-collision guidance directing users to password login and Settings. Cancellation leaves the screen idle without error. Network/provider failures remain retryable and do not fabricate a session.
- [ ] In Settings, show linked status without raw subject. For unlinked password users, present a secure password-confirmation sheet before explicit Google acquisition/linking. Clear password on completion, cancellation and dismissal. Same-email requirement must be clear. Google-only users see linked status, not a password prompt or unlink action.
- [ ] Hide Google controls on unsupported platforms/Expo Go or absent configuration. Preserve all existing email/register/Telegram/logout flows and current Indonesian UI conventions.

Verification: TypeScript and physical Android smoke tests, readable busy/error states, TalkBack labels, duplicate-tap guard, cancellation, password confirmation and existing Telegram controls.

### Step 8: Update existing setup and architecture docs
**Owner: documenter subagent, parallel batch B with Step 7. Depends on Step 6 and Step 1 specification.**

- [ ] Update only existing `PRODUCT.md`, `README.md`, `docs/architecture.md`, `docs/mobile-quickstart.md`; do not create the missing user-owned feature specification.
- [ ] Document Google Cloud Web versus Android client roles, actual signing SHA-1 variants, tester/consent setup, matching client-ID environment variables, native rebuild requirement and physical-device verification.
- [ ] State that no client secret/Firebase/Google offline tokens are needed. Explain explicit linking, email collisions, NULL passwords for Google users, no unlink/password recovery in this MVP, and existing per-user logout semantics.
- [ ] Replace misleading Expo Go Google expectations with the native-build exception; preserve existing email-only development instructions. Include backend-first rollout and additive migration rollback guidance below.

Verification: commands match actual tested build setup and package versions; no credentials, speculative iOS support or unsupported compatibility claims.

### Step 9: Security review, full verification and rollout gate
**Owner: reviewer subagent read-only, then builder inline for fixes and integration. Depends on Steps 7-8.**

- [ ] Review all auth/schema/mobile changes against the user specification and this contract. Require findings for audience bypass, email auto-linking, subject reassignment, PostgreSQL aborted transactions, SQLite partial writes, Telegram regression, logs/token exposure and logout failures.
- [ ] Builder fixes findings inline, verifies each fix, and reruns full checks below. Mechanical/bulk changes stay one bounded builder script. Never allow a reviewer to edit application files.
- [ ] Run the complete physical Android acceptance matrix on the preview APK and supported dev build. Record device/build fingerprint, masked client configuration, provider/backend outcomes, and exact skipped gates. Play signing verification is mandatory only when Play distribution is being released.
- [ ] Deploy backend with migration/config before distributing the new APK. Take a production backup through existing runbook with user approval before the first production migration. Keep password authentication available throughout.
- [ ] Rollback application to the previous build and disable Google endpoints by clearing backend Google configuration if necessary. Keep additive schema/identity data; do not drop `google_sub`, strip identities, or downgrade schema. Existing issued JWTs still follow current session rules. Tell Google-only users Google login will be temporarily unavailable during provider/config rollback.

Verification: no unresolved high-severity ownership/security finding; all automated suites and required device gates green before calling this feature complete.

## Delegation Strategy

| Step | Owner | Parallel batch | Why |
| --- | --- | --- | --- |
| 1 | builder inline + user inputs | - | Specification/cloud ownership needs current context and user control. |
| 2 | builder inline | - | Native spike and all dependency/config/lockfile edits need one owner. |
| 3 | builder inline | - | Coupled dual-dialect migration and user invariants; small shared core. |
| 4 | builder inline | A | Own endpoint implementation and shared config; keep transaction context local. |
| 5 | tester subagent | A | Independent security tests, only new exclusive test files. |
| 6 | builder inline | - | Stabilize API/session/native service contracts before UI delegation. |
| 7 | designer subagent | B | Bounded native UI/accessibility, exclusive screen/component files. |
| 8 | documenter subagent | B | Existing documentation only, no UI/shared source overlap. |
| 9 | reviewer subagent, then builder inline | - | Read-only security gate; builder owns fixes, final verification and merge. |

Batch A dispatches Steps 4 and 5 together after Step 3. Batch B dispatches Steps 7 and 8 together after Step 6. Each batch uses one dispatch message; do not create parallel feature branches for these coupled tasks. Builder uses working-tree isolation or exclusive file ownership to prevent collisions. Test/UI/documentation agents do not change dependency manifests, lockfiles or generated native projects. No mutating agents are dispatched by the planner.

All bulk/config/version assertion edits across more than two files belong to builder inline using one bounded script. No delegation decision call is needed because file ownership is explicit.

## Acceptance Criteria

- A new Android Google user receives a first-party JWT pair, one persistent user and exactly one set of default categories, without a fabricated password.
- Repeat Google sign-in opens the same financial account. Unknown subjects with existing emails never auto-link or create duplicate accounts.
- A password user can explicitly link the matching Google identity with password confirmation, then sign in either way. Wrong email/password, claimed subjects and replacement attempts cannot change ownership.
- Signature/audience/issuer/expiry/email verification and payload limits fail closed. Outages, throttling, cancellations and missing Play Services do not create a session or leak credentials.
- Both dialects upgrade v5 to v6 idempotently and enforce subject uniqueness; simultaneous requests never create partial/duplicate identities or unhandled 500s.
- Password login/register/refresh/logout, Telegram linking/unlinking, reports, debts and recurring flows remain green. Provider sign-out failure cannot retain app tokens.
- Native RN 0.88 compatibility, Google Cloud package/SHA-1 registration and a physical APK flow are demonstrated. No Expo/RN downgrade or fake iOS configuration is hidden in the implementation.
- Google controls do not break password-only app startup on unsupported platforms/Expo Go or absent Google configuration.
- No Google token/password/client secret is persisted, logged, bundled as a secret, or returned in profile responses. `google_sub` stays private backend identity data.

## Verification / Tests

Run with test fixtures and temporary databases only:

```bash
source .venv/bin/activate
pip install -e '.[dev]' -r requirements-dev.txt
ruff check .
pytest
# Set POSTGRES_TEST_URL to an isolated LOCAL test database before running:
pytest tests/test_postgres_portability.py
cd mobile
yarn install --frozen-lockfile
npx tsc --noEmit
npx expo-doctor
# Only after Step 2 establishes a supported package/version pair:
node node_modules/react-native-nitro-google-signin/scripts/validate-compatibility.js
npx expo config --type prebuild
# In the disposable spike/local Android environment only:
npx expo prebuild --platform android
npx expo run:android
# Alternatively use the verified EAS profile from Step 2:
npx eas-cli build --platform android --profile preview
```

Do not use a Supabase production URL for portability tests. If local PostgreSQL/native tooling/EAS/device/OAuth credentials are unavailable, label those gates blocked, not passed. The previous conversation's test count was inferred from test definitions rather than a precise pytest summary; collect an actual current summary for release evidence instead of copying that count.

Android manual matrix: new Google account; returning Google account; existing password email collision; password-confirmed linking; wrong-account linking; chooser cancellation; no Play Services; offline/API outage; duplicate taps; app restart/session refresh; logout/native failure; Google account switch; Telegram link/unlink on a Google-only user. Verify no token values appear in logs or crash messages.

## Git (branch: feature/google-auth-android)

- Planner commits only `plan/google-auth-android.md` on `main` before handoff. No implementation code is changed in planning.
- Builder creates `feature/google-auth-android` from that committed main state. Keep milestone commits for verified native setup, schema, backend/tests, mobile/UI, and documentation.
- Never commit `.env`, signing keys, actual private credentials, generated build directories or temporary spike debug code. Do not force-push or silently rewrite old migration commits.
- After every required gate is green, builder may integrate this single sequential workstream using the normal builder workflow. Remove the plan only after all steps are verified; blocked native/device gates mean the plan stays.

## Integration Notes

One plan covers the whole feature because mobile configuration, new auth endpoints, user schema, identity policy and acceptance criteria are coupled. There are no sibling plans or independent merge order.

Likely overlaps with other work: `finance_core/db/users.py`, both migration files, `backend/app/routes/auth.py`, `schemas.py`, mobile auth/Settings screens, dependency manifests and Yarn lockfile. Rebase/review any overlapping auth change before execution; if another migration lands first, use the next unused version consistently and rerun both upgrade suites.

If this work later becomes multiple parallel branches, branches must not self-merge. User runs `/integrate` in a builder session from main after all branches are verified; integrate schema/backend before Android client changes.

## Research Sources

Checked 2026-11-07 with Context7 and primary documentation:
- https://docs.expo.dev/guides/google-authentication/ (native builds, Credential Manager versus deprecated legacy SDK).
- https://react-native-nitro-google-sign-in.github.io/docs/setup/expo (explicit Android Web client ID, no-Firebase setup and plugin limitations).
- https://react-native-nitro-google-sign-in.github.io/docs/getting-started/compatibility and https://raw.githubusercontent.com/react-native-nitro-google-sign-in/google-signin/main/compatibility.json (RN 0.88 not listed).
- https://raw.githubusercontent.com/react-native-nitro-google-sign-in/google-signin/main/plugin/withNitroGoogleSignIn.js (unconditional no-Firebase iOS scheme validation).
- https://react-native-nitro-google-sign-in.github.io/docs/guide/usage and /docs/guide/google-sign-in-button (response/cancellation/sign-out/branded controls).
- https://developers.google.com/identity/sign-in/android/backend-auth (server verification, subject identity, third-party email authority caveat).
- https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html (explicit audience, verifier errors, certificate caching).

## Read-Only Design Review Disposition

A security reviewer inspected the existing repository during planning. Accepted concerns are incorporated above: plain SQLite column plus separate unique index, dual-dialect version parity, avoiding nested SQLite commits, portable rollback/uniqueness recovery, explicit user mapping, conditional linking writes, lazy PostgreSQL `lastval()` ownership, bounded verifier transport, existing string error format, and platform-safe native imports.

The reviewer suggested allowing Google linking without a password when the current account has no password. Do not adopt that change in this MVP. New Google-only users are linked at creation and log in by their stored subject; they never need to link again. A different Google subject colliding with their email must remain blocked, not replace or supplement their identity. Existing password accounts follow the user's required password-authenticated explicit linking policy. Account recovery, a changed provider identity and adding alternate identities require a separately approved feature, not a permissive fallback.

Do not expand this work into fixing every pre-existing nested transaction or Telegram exception path. New Google paths must own correct boundaries, and narrowly necessary Telegram identity guards receive regression tests.
