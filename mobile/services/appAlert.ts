/** In-tree confirmations disappear when privacy state changes. */
import type { AlertButton } from 'react-native';
import { getAppLockState, subscribeAppLock } from './appLock';
import { isAuthenticated, subscribeSession } from './session';

interface Dialog {
  title: string;
  message?: string;
  buttons: AlertButton[];
  host: string;
  generation: number;
}
let dialog: Dialog | null = null;
let generation = 0;
const hosts: string[] = [];
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((listener) => listener());
function gated(): boolean {
  const lock = getAppLockState();
  return !isAuthenticated() || !lock.ready || lock.locked || lock.covered;
}
function invalidate(): void {
  if (!gated()) return;
  generation += 1;
  dialog = null;
  notify();
}
subscribeAppLock(invalidate);
subscribeSession(invalidate);

export function registerAppAlertHost(host: string): () => void {
  if (host === 'root') hosts.unshift(host);
  else hosts.push(host);
  return () => {
    const index = hosts.indexOf(host);
    if (index >= 0) hosts.splice(index, 1);
    if (dialog?.host === host) { dialog = null; generation += 1; notify(); }
  };
}
export const getAppAlert = () => dialog;
export function subscribeAppAlert(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
export const AppAlert = {
  alert(title: string, message?: string, buttons?: AlertButton[]): void {
    if (gated()) return;
    dialog = { title, message, buttons: buttons ?? [{ text: 'OK' }],
      host: hosts[hosts.length - 1] ?? 'root', generation };
    notify();
  },
};
export function dismissAppAlert(): void { dialog = null; notify(); }
export function pressAppAlert(index: number): void {
  const current = dialog;
  dialog = null;
  notify();
  if (!current || current.generation !== generation || gated()) return;
  current.buttons[index]?.onPress?.();
}
