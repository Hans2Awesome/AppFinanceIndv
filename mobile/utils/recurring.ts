/** Labels and one-line descriptions for recurring schedules. */

import { RecurringFrequency, TransactionType } from '../types';

export const WEEKDAY_LABELS = [
  'Senin',
  'Selasa',
  'Rabu',
  'Kamis',
  'Jumat',
  'Sabtu',
  'Minggu',
] as const;

export const WEEKDAY_SHORT = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min'] as const;

export function describeFrequency(
  frequency: RecurringFrequency,
  dayOfWeek?: number | null,
  dayOfMonth?: number | null
): string {
  if (frequency === 'weekly') {
    const index = dayOfWeek ?? 0;
    return `Setiap ${WEEKDAY_LABELS[index] ?? WEEKDAY_LABELS[0]}`;
  }
  return `Setiap tanggal ${dayOfMonth ?? 1}`;
}

export function recurringTitle(
  type: TransactionType,
  categoryName?: string | null,
  note?: string | null
): string {
  if (note?.trim()) return note.trim();
  if (categoryName?.trim()) return categoryName.trim();
  return type === 'income' ? 'Pemasukan rutin' : type === 'investment' ? 'Investasi rutin' : 'Pengeluaran rutin';
}

export function typeLabel(type: TransactionType): string {
  if (type === 'income') return 'Pemasukan';
  if (type === 'investment') return 'Investasi';
  return 'Pengeluaran';
}