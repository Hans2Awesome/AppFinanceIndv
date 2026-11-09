# Android Keyboard Layout Implementation Plan

> **For agentic workers:** Use the plans skill execute mode, task-by-task. Start implementation only after user confirmation.

**Goal:** Keep form fields and primary actions reachable when the Android keyboard opens.

**Architecture:** Reuse the existing Screen and Sheet primitives. Give each screen or modal one bounded keyboard-avoidance container, with a scrollable body and an accessible footer. Preserve the existing ledger visual system.

**Tech Stack:** Expo 58, React Native 0.88, Expo Router, TypeScript.

## Integration Notes

Integrated into local `main` on 2026-11-09 after `feature/google-auth-android`. Merge commit: `d4dc6e7`. Overlap in authentication screens was already present in the branch ancestry; both merges completed without conflicts. The auth preflight fix was merged into this branch before verification. Ruff, TypeScript, and the Python suite pass on both verified branch tips and merged main (302 passed, 6 skipped because local PostgreSQL was unavailable). The prior TypeScript failure recorded below is resolved by `a1286d5`. No APK, Gradle, or EAS build was run. Keep this plan for the remaining broader device/accessibility matrix and native Google linking checks; all five user acceptance tests passed on the reported Realme device.

## Global Constraints

- Do not build an APK on this VPS. Do not run Gradle, Expo native builds, or EAS Build.
- Do not add dependencies or change finance/authentication behavior.
- Preserve DESIGN.md colors, typography, spacing, and accessibility labels.
- Run heavyweight verification sequentially, with at most two workers.
- Physical Android keyboard behavior requires device verification; do not report static checks as runtime validation.

## Findings

- Screen does not provide keyboard avoidance for transaction entry or other shared screens.
- Sheet leaves KeyboardAvoidingView behavior undefined on Android and its dock has no full-height constraint.
- Login and registration already wrap Screen with KeyboardAvoidingView. Avoid nested avoidance after updating Screen.
- The generated Android manifest already uses adjustResize. Expo edge-to-edge layouts still require explicit keyboard avoidance.
- Bottom tabs do not hide when the keyboard opens.

## Visual and Accessibility Direction

Keep the closed-keyboard appearance unchanged. When the keyboard opens, shrink the available form area, retain the primary action above the keyboard, and let long content scroll. Preserve field labels, screen-reader order, touch targets, and tap handling. Do not solve overlap by adding fixed keyboard-height padding.

## Task 1: Shared Screen Keyboard Avoidance

**Files:**
- Modify: mobile/components/ui/Screen.tsx
- Modify: mobile/app/(auth)/login.tsx
- Modify: mobile/app/(auth)/register.tsx
- Modify: mobile/app/(tabs)/_layout.tsx

- [x] Capture the baseline with `cd mobile && ./node_modules/.bin/tsc --noEmit`. Existing failure: services/googleAuth.android.ts:34, TS2322, string | undefined is not assignable to string.
- [x] Wrap Screen content and its footer in a flex-constrained KeyboardAvoidingView, using padding on iOS and height on Android.
- [x] Keep the Screen ScrollView bounded and preserve keyboardShouldPersistTaps="handled".
- [x] Remove redundant login/register avoidance wrappers and their unused imports/styles using one mechanical edit.
- [x] Set tabBarHideOnKeyboard to true so tabs do not consume form space.
- [x] Run TypeScript checking again and inspect the diff for nested avoidance and unrelated changes. Same single pre-existing diagnostic; no new errors.

Verification note: a dependency-free Node check transpiled Screen with the installed TypeScript compiler and mocked React Native elements. Six composition cases passed: Android/iOS/web, each with scroll enabled and disabled. Assertions covered the avoidance behavior, flex-constrained body, footer placement, and keyboard tap handling. This is a structural check, not a rendered UI or keyboard test.

## Task 2: Bounded Modal Keyboard Avoidance

**Files:**
- Modify: mobile/components/ui/Sheet.tsx
- Inspect: mobile/components/debts/CreateDebtModal.tsx
- Inspect: mobile/components/debts/DebtDetailModal.tsx
- Inspect: mobile/components/recurring/RecurringFormModal.tsx
- Modify: mobile/components/auth/LinkGoogleSheet.tsx

- [x] Set Sheet KeyboardAvoidingView to padding on iOS and height on Android.
- [x] Give its dock flex: 1 with bottom alignment so maxHeight and body flexShrink resolve inside the visible area. Keep the root top-aligned so the height-reduced dock does not shift back under the keyboard.
- [x] Preserve the header and footer outside the shrinking scroll body; confirm all form bodies declare shrinking scroll layouts. Device behavior remains unverified.
- [x] Run TypeScript checking and `git diff --check`. Diff whitespace check passes; TypeScript retains its baseline failure.
- [x] Request reviewer audit of keyboard layout constraints and accessibility regressions.
- [x] Resolve the review finding: make the Google linking sheet body scrollable and shrinkable while retaining its sticky actions.

Review notes: device testing must check Android modal window/status-bar coordinates and tab-hide timing for footer overlap or stale blank space. Do not introduce speculative offsets before reproducing a coordinate mismatch. Native headers are currently hidden; any future native-header screen must review its keyboardVerticalOffset.

## Task 3: Runtime Verification Handoff

Status: user acceptance tests 1-5 passed in Expo Go on the device below. No device tests were run on this VPS. Native builds are intentionally excluded by the user. The broader device/accessibility matrix and native Google linking remain unverified; retain this plan to track those limitations.

### User Device Results, 2026-11-09

Device: Realme 9 Pro Plus, Android 14, Microsoft SwiftKey AI Keyboard, Expo Go.

- Test 1: registration passes. Login oscillates vertically while its password contains text; an empty password remains stable.
- Tests 2-5: quick input, transaction entry, debt/payment UI, and recurring schedules pass as reported by the user.
- Follow-up: Screen accepts a keyboardBehavior override. Login alone uses padding instead of height to avoid the height-mode layout feedback path. Other tested screens retain their existing behavior. This is a targeted candidate fix and requires repeating login testing on the same device.
- Login retest: user reported "Uji no1 ulang Oke" after the padding override. All five user acceptance tests now pass on this device. Twelve Screen composition checks passed after the override. TypeScript still reports only the pre-existing services/googleAuth.android.ts:34 diagnostic.
- Google linking is not covered by Expo Go; its native module requires a compatible development build.

- [ ] On an Android device outside this VPS, test login, registration, quick input, transaction entry, debt creation, repayment, recurring schedules, and Google linking.
- [ ] Test a compact portrait viewport and a larger phone, with gesture and three-button navigation where available.
- [ ] Focus the first and last fields, switch numeric/text keyboards, scroll to the final field, and tap the primary action once while the keyboard is open.
- [ ] Dismiss the keyboard using Back, reopen it, and close/reopen modals. Check for stale blank space, offscreen actions, lost focus, and changed field values.
- [ ] Check TalkBack labels/focus order and runtime warnings on the test device. Record unavailable checks explicitly.

Delete this plan only after every verification step is green.
