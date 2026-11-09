/** Device-local privacy gate. Never stores or sends a plaintext PIN. */
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const KEY = 'finance.appLock.v1';
const PENDING_KEY = 'finance.appLock.pendingDisable.v1';
const OPTIONS = { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY };
const STORAGE_ERROR = 'Penyimpanan aman tidak tersedia. Coba lagi atau keluar dan masuk ulang.';

interface LockRecord {
  version: 1;
  secret: string;
  verifier: string;
  biometrics: boolean;
  failures: number;
  retryAt: number;
}

export interface AppLockState {
  ready: boolean;
  enabled: boolean;
  biometricsEnabled: boolean;
  locked: boolean;
  covered: boolean;
  busy: boolean;
  error: string | null;
  storageError: boolean;
  retryAt: number;
  failedAttempts: number;
  supported: boolean;
}

let state: AppLockState = {
  ready: false, enabled: false, biometricsEnabled: false, locked: true,
  covered: false, busy: false, error: null, storageError: false, retryAt: 0, failedAttempts: 0,
  supported: Platform.OS !== 'web',
};
let record: LockRecord | null = null;
let authenticated = false;
let visibility = 'active';
let generation = 0;
let running = false;
let biometricPrompt = false;
let storageFailed = false;
const listeners = new Set<() => void>();

export function getAppLockState(): AppLockState { return state; }
export function subscribeAppLock(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
function publish(patch: Partial<AppLockState>): void {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
}
function fields(value: LockRecord | null): Partial<AppLockState> {
  return {
    enabled: value !== null, biometricsEnabled: value?.biometrics ?? false,
    failedAttempts: value?.failures ?? 0, retryAt: value?.retryAt ?? 0,
  };
}
function failStorage(): never {
  storageFailed = true;
  publish({ locked: true, error: STORAGE_ERROR, storageError: true });
  throw new Error(STORAGE_ERROR);
}
function parseRecord(raw: string): LockRecord {
  const value = JSON.parse(raw);
  if (value?.version !== 1 || !/^[0-9a-f]{64}$/.test(value.secret) ||
      !/^[0-9a-f]{64}$/.test(value.verifier) || typeof value.biometrics !== 'boolean' ||
      !Number.isSafeInteger(value.failures) || value.failures < 0 || value.failures > 5 ||
      !Number.isSafeInteger(value.retryAt) || value.retryAt < 0 ||
      (value.failures === 5 && value.retryAt === 0)) {
    throw new Error('Invalid app lock record');
  }
  return value;
}
function validPin(pin: string): void {
  if (!/^[0-9]{6}$/.test(pin)) throw new Error('PIN harus terdiri dari 6 digit.');
}
async function digest(pin: string, secret: string): Promise<string> {
  // Native modules load lazily so older installed binaries can still sign in.
  const crypto = require('expo-crypto') as typeof import('expo-crypto');
  return crypto.digestStringAsync(crypto.CryptoDigestAlgorithm.SHA256,
    `finance.appLock.v1:${secret}:${pin}`);
}
function equal(left: string, right: string): boolean {
  let difference = left.length ^ right.length;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}
async function persist(next: LockRecord | null): Promise<void> {
  try {
    if (next) await SecureStore.setItemAsync(KEY, JSON.stringify(next), OPTIONS);
    else await SecureStore.deleteItemAsync(KEY);
  } catch { failStorage(); }
  record = next;
  publish(fields(next));
}

/** Read errors and corrupt records are never interpreted as lock disabled. */
export async function hydrateAppLock(): Promise<void> {
  if (running) return;
  running = true;
  generation += 1;
  publish({ ready: false, busy: true, locked: true, error: null });
  try {
    let raw = Platform.OS === 'web' ? null : await SecureStore.getItemAsync(KEY);
    if (Platform.OS !== 'web') {
      const pending = await SecureStore.getItemAsync(PENDING_KEY);
      if (pending !== null) {
        // A failed/cancelled disable must survive even a failed rollback write.
        const previous = parseRecord(pending);
        await SecureStore.setItemAsync(KEY, JSON.stringify(previous), OPTIONS);
        await SecureStore.deleteItemAsync(PENDING_KEY);
        raw = JSON.stringify(previous);
      }
    }
    const next = raw === null ? null : parseRecord(raw);
    record = next;
    storageFailed = false;
    publish({ ...fields(next), ready: true, locked: authenticated && next !== null,
      covered: visibility !== 'active', error: null, storageError: false });
  } catch {
    storageFailed = true;
    publish({ ready: true, locked: true, error: STORAGE_ERROR, storageError: true });
  } finally {
    running = false;
    publish({ busy: false });
  }
}

export function setAppLockSession(next: boolean): void {
  if (authenticated === next) return;
  authenticated = next;
  generation += 1;
  publish({ locked: next && (record !== null || !state.ready || storageFailed),
    covered: visibility !== 'active', error: storageFailed ? STORAGE_ERROR : null });
}

export function handleAppLockState(next: string): void {
  visibility = next;
  if (next !== 'active') {
    // OS biometric dialogs can cause 'inactive'. A genuine background always
    // invalidates authentication, even when a native prompt is still pending.
    if (next === 'background' || !biometricPrompt) generation += 1;
    publish({ covered: true,
      locked: state.locked || (authenticated && record !== null &&
        (next === 'background' || !biometricPrompt)) });
  } else publish({ covered: false });
}

async function exclusive<T>(operation: (ticket: number) => Promise<T>): Promise<T> {
  if (running) throw new Error('Verifikasi sedang berlangsung.');
  running = true;
  publish({ busy: true, error: null });
  const ticket = generation;
  try { return await operation(ticket); }
  catch (error) {
    publish({ error: error instanceof Error ? error.message : 'Verifikasi gagal.' });
    throw error;
  } finally {
    running = false;
    publish({ busy: false });
  }
}
function active(ticket: number): void {
  if (ticket !== generation || !authenticated || visibility === 'background') {
    throw new Error('Verifikasi dibatalkan. Buka aplikasi dan coba lagi.');
  }
}
function available(ticket: number, needsRecord = true): void {
  active(ticket);
  if (!state.ready || storageFailed || !state.supported) {
    throw new Error(STORAGE_ERROR);
  }
  if (needsRecord && !record) throw new Error('Kunci aplikasi belum diaktifkan.');
  if (Date.now() < state.retryAt) throw new Error('Terlalu banyak PIN salah. Tunggu 30 detik.');
}

async function verify(pin: string, ticket: number): Promise<boolean> {
  available(ticket);
  validPin(pin);
  const current = record!;
  const actual = await digest(pin, current.secret);
  active(ticket);
  if (!equal(actual, current.verifier)) {
    const failures = (current.retryAt > 0 && Date.now() >= current.retryAt ? 0 : current.failures) + 1;
    await persist({ ...current, failures, retryAt: failures >= 5 ? Date.now() + 30_000 : 0 });
    active(ticket);
    publish({ error: failures >= 5 ? 'Terlalu banyak PIN salah. Tunggu 30 detik.' : 'PIN salah.' });
    return false;
  }
  // Clearing the retry budget is durable before the gate opens.
  await persist({ ...current, failures: 0, retryAt: 0 });
  active(ticket);
  return true;
}
async function requirePin(pin: string, ticket: number): Promise<void> {
  if (!await verify(pin, ticket)) throw new Error(state.error || 'PIN salah.');
  if (state.locked) throw new Error('Buka kunci aplikasi sebelum mengubah pengaturan.');
}

/** An authenticated setting change must not finish after its proof expires. */
async function persistSetting(next: LockRecord | null, ticket: number): Promise<void> {
  const previous = record;
  await persist(next);
  if (ticket !== generation || !authenticated || visibility === 'background') {
    await persist(previous);
    if (next === null && previous !== null) {
      try { await SecureStore.deleteItemAsync(PENDING_KEY); }
      catch { failStorage(); }
    }
    publish({ locked: true });
    throw new Error('Perubahan dibatalkan. Buka aplikasi dan coba lagi.');
  }
}

export async function getBiometricAvailability(): Promise<boolean> {
  if (Platform.OS === 'web') return false;
  try {
    const native = require('expo-local-authentication') as typeof import('expo-local-authentication');
    return await native.hasHardwareAsync() && await native.isEnrolledAsync() &&
      await native.getEnrolledLevelAsync() === native.SecurityLevel.BIOMETRIC_STRONG;
  } catch { return false; }
}
async function biometricProof(ticket: number): Promise<boolean> {
  if (!await getBiometricAvailability()) throw new Error('Biometrik kuat belum tersedia. Gunakan PIN.');
  active(ticket);
  biometricPrompt = true;
  try {
    const native = require('expo-local-authentication') as typeof import('expo-local-authentication');
    const result = await native.authenticateAsync({
      promptMessage: 'Buka kunci FinanceApp', cancelLabel: 'Gunakan PIN',
      fallbackLabel: '', disableDeviceFallback: true, biometricsSecurityLevel: 'strong',
    });
    active(ticket);
    return result.success === true;
  } finally { biometricPrompt = false; }
}

export async function enableAppLock(pin: string): Promise<void> {
  return exclusive(async (ticket) => {
    available(ticket, false);
    if (record) throw new Error('Kunci aplikasi sudah aktif.');
    validPin(pin);
    const crypto = require('expo-crypto') as typeof import('expo-crypto');
    const bytes = await crypto.getRandomBytesAsync(32);
    const secret = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    const verifier = await digest(pin, secret);
    active(ticket);
    await persist({ version: 1, secret, verifier, biometrics: false, failures: 0, retryAt: 0 });
    // If the app went to background during the write, leave the new lock closed.
    publish({ locked: ticket !== generation || visibility !== 'active' });
  });
}
export async function unlockWithPin(pin: string): Promise<boolean> {
  try {
    return await exclusive(async (ticket) => {
      if (!await verify(pin, ticket)) return false;
      publish({ locked: false, error: null });
      return true;
    });
  } catch { return false; }
}
export async function unlockWithBiometrics(): Promise<boolean> {
  try {
    return await exclusive(async (ticket) => {
      available(ticket);
      if (!record!.biometrics) throw new Error('Aktifkan biometrik lewat pengaturan kunci aplikasi.');
      if (!await biometricProof(ticket)) {
        publish({ error: 'Biometrik dibatalkan atau gagal. Gunakan PIN.' });
        return false;
      }
      await persist({ ...record!, failures: 0, retryAt: 0 });
      active(ticket);
      publish({ locked: false, error: null });
      return true;
    });
  } catch { return false; }
}
export async function changeAppLockPin(currentPin: string, nextPin: string): Promise<void> {
  return exclusive(async (ticket) => {
    validPin(nextPin);
    await requirePin(currentPin, ticket);
    const crypto = require('expo-crypto') as typeof import('expo-crypto');
    const bytes = await crypto.getRandomBytesAsync(32);
    const secret = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    const verifier = await digest(nextPin, secret);
    active(ticket);
    await persistSetting({ ...record!, secret, verifier }, ticket);
  });
}
export async function disableAppLock(currentPin: string): Promise<void> {
  return exclusive(async (ticket) => {
    await requirePin(currentPin, ticket);
    try {
      await SecureStore.setItemAsync(PENDING_KEY, JSON.stringify(record), OPTIONS);
    } catch { failStorage(); }
    await persistSetting(null, ticket);
    // Once this final commit starts, the already-authorized disable is committed.
    // Until it succeeds, hydration recovers the pending enabled record.
    try { await SecureStore.deleteItemAsync(PENDING_KEY); }
    catch { failStorage(); }
    publish({ locked: false });
  });
}
export async function setAppLockBiometrics(currentPin: string, enabled: boolean): Promise<void> {
  return exclusive(async (ticket) => {
    await requirePin(currentPin, ticket);
    if (enabled && !await biometricProof(ticket)) throw new Error('Biometrik dibatalkan atau gagal.');
    active(ticket);
    await persistSetting({ ...record!, biometrics: enabled }, ticket);
  });
}

/** Fresh credential login can recover a forgotten device PIN. Never call on refresh. */
export async function resetAppLockAfterSignIn(): Promise<void> {
  return exclusive(async () => {
    generation += 1;
    if (Platform.OS !== 'web') {
      await persist(null);
      try { await SecureStore.deleteItemAsync(PENDING_KEY); }
      catch { failStorage(); }
    }
    else record = null;
    storageFailed = false;
    publish({ ...fields(null), ready: true, locked: false, error: null, storageError: false });
  });
}
