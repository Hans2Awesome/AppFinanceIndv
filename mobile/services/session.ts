/**
 * Session storage for the mobile app.
 *
 * Tokens live in SecureStore on native platforms. The web build falls back to
 * memory because SecureStore has no web implementation; that means a page
 * reload logs the user out on web, which is intentional rather than silently
 * writing tokens to localStorage.
 */

import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { setAppLockSession } from './appLock';

const ACCESS_TOKEN_KEY = 'finance.accessToken';
const REFRESH_TOKEN_KEY = 'finance.refreshToken';

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

let accessToken: string | null = null;
let refreshToken: string | null = null;
let revision = 0;
let storageQueue: Promise<void> = Promise.resolve();

/** Logout deletions run after any earlier token write, never before it. */
function persistInOrder(write: () => Promise<void>): Promise<void> {
  const pending = storageQueue.then(write);
  storageQueue = pending.catch(() => {});
  return pending;
}

const listeners = new Set<() => void>();

function notify(): void {
  setAppLockSession(isAuthenticated());
  listeners.forEach((listener) => listener());
}

export function subscribeSession(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function getRefreshToken(): string | null {
  return refreshToken;
}

export function isAuthenticated(): boolean {
  return accessToken !== null;
}

export async function hydrateSession(): Promise<void> {
  if (Platform.OS === 'web') {
    return;
  }

  const ticket = revision;
  try {
    await storageQueue;
    const access = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
    const refresh = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
    if (ticket !== revision) return;
    accessToken = access;
    refreshToken = refresh;
  } catch {
    if (ticket !== revision) return;
    accessToken = null;
    refreshToken = null;
  }
  notify();
}

export async function saveSession(tokens: TokenPair): Promise<void> {
  const ticket = ++revision;
  accessToken = tokens.access_token;
  refreshToken = tokens.refresh_token;

  if (Platform.OS !== 'web') {
    try {
      await persistInOrder(async () => {
        if (ticket !== revision) return;
        await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, tokens.access_token);
        if (ticket !== revision) return;
        await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, tokens.refresh_token);
      });
    } catch {
      // Keep the in-memory session even if the device store is unavailable.
    }
  }
  notify();
}

export async function clearSession(): Promise<void> {
  revision += 1;
  accessToken = null;
  refreshToken = null;
  // Immediately invalidate app-lock proofs, before any native I/O can finish.
  notify();

  if (Platform.OS !== 'web') {
    try {
      await persistInOrder(async () => {
        await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
        await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
      });
    } catch {
      // Nothing else to clean up.
    }
  }
}
