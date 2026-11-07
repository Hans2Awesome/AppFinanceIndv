/**
 * Google sign-in fallback for web, iOS and Expo Go.
 *
 * This file is chosen by Metro whenever the Android variant is not active, so
 * the native Credential Manager module is never bundled or evaluated there.
 */

export async function isGoogleAuthAvailable(): Promise<boolean> {
  return false;
}

export async function requestGoogleIdToken(): Promise<string | null> {
  throw new Error('GOOGLE_UNAVAILABLE');
}

export async function signOutGoogle(): Promise<void> {
  return;
}
