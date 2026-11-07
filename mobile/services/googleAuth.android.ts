/**
 * Google sign-in token acquisition, Android only.
 *
 * The native Credential Manager module is imported lazily: loading it at module
 * scope would crash Android Expo Go builds that do not contain the native code.
 * Web and iOS use the platform-neutral `googleAuth.ts` fallback instead.
 */

import type * as GoogleModuleTypes from 'react-native-nitro-google-signin';

const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;

type GoogleModule = typeof GoogleModuleTypes;

let modulePromise: Promise<GoogleModule | null> | null = null;

function loadGoogleModule(): Promise<GoogleModule | null> {
  if (!webClientId) {
    return Promise.resolve(null);
  }
  if (!modulePromise) {
    modulePromise = import('react-native-nitro-google-signin').catch(() => null);
  }
  return modulePromise;
}

/** True when the Google button can be shown on this build and device. */
export async function isGoogleAuthAvailable(): Promise<boolean> {
  const module = await loadGoogleModule();
  if (!module) {
    return false;
  }
  try {
    module.GoogleOneTapSignIn.configure({ webClientId });
    await module.GoogleOneTapSignIn.checkPlayServices();
    return true;
  } catch {
    return false;
  }
}

/**
 * Run the native sign-in flow and return a Google ID token.
 *
 * Resolves to null when the user cancels. Throws a stable Error code for real
 * failures so the caller can show a message.
 */
export async function requestGoogleIdToken(): Promise<string | null> {
  const module = await loadGoogleModule();
  if (!module || !webClientId) {
    throw new Error('GOOGLE_UNAVAILABLE');
  }

  const {
    GoogleOneTapSignIn,
    isErrorWithCode,
    isNoSavedCredentialFoundResponse,
    isSuccessResponse,
    statusCodes,
  } = module;

  GoogleOneTapSignIn.configure({ webClientId });
  await GoogleOneTapSignIn.checkPlayServices();

  let response;
  try {
    response = await GoogleOneTapSignIn.signIn();
    if (isNoSavedCredentialFoundResponse(response)) {
      response = await GoogleOneTapSignIn.createAccount();
    }
    if (isNoSavedCredentialFoundResponse(response)) {
      response = await GoogleOneTapSignIn.presentExplicitSignIn();
    }
  } catch (error) {
    if (isErrorWithCode(error) && error.code === statusCodes.SIGN_IN_CANCELLED) {
      return null;
    }
    throw error;
  }

  if (!isSuccessResponse(response)) {
    return null;
  }
  const idToken = response.data.idToken;
  if (!idToken) {
    throw new Error('GOOGLE_NO_ID_TOKEN');
  }
  return idToken;
}

/** Best-effort native sign-out. Never blocks the app logout on failure. */
export async function signOutGoogle(): Promise<void> {
  const module = await loadGoogleModule();
  if (!module) {
    return;
  }
  try {
    await module.GoogleOneTapSignIn.signOut();
  } catch {
    // Signing out of the app must not fail because Google sign-out errored.
  }
}