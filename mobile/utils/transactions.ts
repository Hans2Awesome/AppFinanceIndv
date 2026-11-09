/**
 * Pure validation, diffing, pagination, and timestamp helpers for transaction
 * editing and change history.
 *
 * Kept dependency-free so unit tests can run directly inside a Node VM.
 */

import type {
  Transaction,
  TransactionAuditAction,
  TransactionAuditReason,
  TransactionAuditSource,
  TransactionHistoryEntry,
  TransactionSnapshot,
  TransactionType,
  TransactionUpdatePayload,
} from '../types';

export const MAX_TRANSACTION_NOTE_LENGTH = 500;
export const MAX_ASSET_NAME_LENGTH = 80;

const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Parse numeric digits from a raw amount input string. */
export function parseTransactionAmount(raw: string): number {
  const input = String(raw ?? '').trim();
  if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+)$/.test(input)) return NaN;
  const cleaned = input.replace(/\./g, '');
  if (!cleaned) {
    return NaN;
  }
  const value = Number.parseInt(cleaned, 10);
  return Number.isSafeInteger(value) ? value : NaN;
}

/** Validate that a transaction amount is a positive integer. */
export function validateTransactionAmount(raw: string | number): string | null {
  const amount = typeof raw === 'number' ? raw : parseTransactionAmount(raw);
  if (!Number.isSafeInteger(amount) || amount <= 0) {
    return 'Nominal harus lebih dari 0.';
  }
  return null;
}

/** Validate a calendar date in strict YYYY-MM-DD format. */
export function isValidIsoDate(value: string): boolean {
  const trimmed = String(value ?? '').trim();
  const match = ISO_DATE_RE.exec(trimmed);
  if (!match) {
    return false;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year < 1900 || year > 2100 || month < 1 || month > 12 || day < 1 || day > 31) {
    return false;
  }
  const check = new Date(Date.UTC(year, month - 1, day));
  return (
    check.getUTCFullYear() === year &&
    check.getUTCMonth() === month - 1 &&
    check.getUTCDate() === day
  );
}

/** Return an Indonesian validation error when transaction_date is invalid. */
export function validateTransactionDate(value: string): string | null {
  if (!isValidIsoDate(value)) {
    return 'Tanggal harus berformat YYYY-MM-DD yang valid.';
  }
  return null;
}

/** Validate optional note length (max 500 characters after trim). */
export function validateTransactionNote(value: string | null | undefined): string | null {
  const trimmed = String(value ?? '').trim();
  if (trimmed.length > MAX_TRANSACTION_NOTE_LENGTH) {
    return `Catatan maksimal ${MAX_TRANSACTION_NOTE_LENGTH} karakter.`;
  }
  return null;
}

/** Validate optional investment asset name length (max 80 characters after trim). */
export function validateAssetName(value: string | null | undefined): string | null {
  const trimmed = String(value ?? '').trim();
  if (trimmed.length > MAX_ASSET_NAME_LENGTH) {
    return `Nama aset maksimal ${MAX_ASSET_NAME_LENGTH} karakter.`;
  }
  return null;
}

export interface TransactionDraftInput {
  amount: string;
  transactionDate: string;
  categoryId: number | null;
  note: string;
  assetName: string;
  type: TransactionType;
}

/** Validate all editable transaction fields together. */
export function validateTransactionDraft(draft: TransactionDraftInput): string | null {
  const amountError = validateTransactionAmount(draft.amount);
  if (amountError) return amountError;

  const dateError = validateTransactionDate(draft.transactionDate);
  if (dateError) return dateError;

  const noteError = validateTransactionNote(draft.note);
  if (noteError) return noteError;

  if (draft.type === 'investment') {
    const assetError = validateAssetName(draft.assetName);
    if (assetError) return assetError;
  }

  return null;
}

/**
 * Build a minimal PUT payload containing only fields that changed, using
 * explicit `null` when clearing nullable fields (`category_id`, `note`, `asset_name`).
 */
export function buildTransactionUpdatePayload(
  original: Pick<
    Transaction,
    'type' | 'amount' | 'transaction_date' | 'category_id' | 'note' | 'asset_name'
  >,
  draft: TransactionDraftInput
): TransactionUpdatePayload {
  const payload: TransactionUpdatePayload = {};

  const nextAmount = parseTransactionAmount(draft.amount);
  if (Number.isFinite(nextAmount) && nextAmount > 0 && nextAmount !== original.amount) {
    payload.amount = nextAmount;
  }

  const nextDate = draft.transactionDate.trim();
  if (nextDate && nextDate !== original.transaction_date) {
    payload.transaction_date = nextDate;
  }

  const originalCategoryId = original.category_id ?? null;
  const nextCategoryId = draft.categoryId ?? null;
  if (nextCategoryId !== originalCategoryId) {
    payload.category_id = nextCategoryId;
  }

  const originalNote = (original.note ?? '').trim() || null;
  const nextNote = draft.note.trim() || null;
  if (nextNote !== originalNote) {
    payload.note = nextNote;
  }

  if (original.type === 'investment') {
    const originalAsset = (original.asset_name ?? '').trim() || null;
    const nextAsset = draft.assetName.trim() || null;
    if (nextAsset !== originalAsset) {
      payload.asset_name = nextAsset;
    }
  }

  return payload;
}

/** Check whether an update payload has at least one modified field. */
export function hasTransactionChanges(payload: TransactionUpdatePayload): boolean {
  return Object.keys(payload).length > 0;
}

/** Determine whether a transaction can be edited (defaults to true unless false). */
export function canEditTransaction(tx: Pick<Transaction, 'can_edit'> | null | undefined): boolean {
  if (!tx) return false;
  return tx.can_edit !== false;
}

/** Determine whether a transaction can be deleted (defaults to true unless false). */
export function canDeleteTransaction(
  tx: Pick<Transaction, 'can_delete'> | null | undefined
): boolean {
  if (!tx) return false;
  return tx.can_delete !== false;
}

/** Human-readable Indonesian label for a transaction type. */
export function transactionTypeLabel(type: TransactionType): string {
  if (type === 'income') return 'Pemasukan';
  if (type === 'investment') return 'Investasi';
  return 'Pengeluaran';
}

/** Human-readable Indonesian label for an audit action. */
export function historyActionLabel(action: TransactionAuditAction): string {
  return action === 'delete' ? 'Dihapus' : 'Diubah';
}

/** Human-readable Indonesian label for an audit source. */
export function historySourceLabel(source: TransactionAuditSource): string {
  if (source === 'telegram') return 'Telegram';
  if (source === 'system') return 'Sistem';
  return 'Aplikasi';
}

/** Human-readable Indonesian label for an audit reason without exposing source_key. */
export function historyReasonLabel(reason: TransactionAuditReason): string {
  switch (reason) {
    case 'debt_sync':
      return 'Sinkronisasi hutang/piutang';
    case 'debt_delete':
      return 'Catatan hutang/piutang dihapus';
    case 'payment_delete':
      return 'Pembayaran hutang/piutang dihapus';
    case 'direct':
    default:
      return 'Perubahan langsung';
  }
}

export interface HistoryFieldChange {
  field: 'amount' | 'category' | 'transaction_date' | 'note' | 'asset_name';
  label: string;
  before: string;
  after: string;
}

function formatRupiahInline(amount: number): string {
  if (!Number.isFinite(amount)) return 'Rp0';
  const formatted = Math.abs(Math.round(amount))
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return (amount < 0 ? '-Rp' : 'Rp') + formatted;
}

const MONTHS_INDO = [
  'Januari',
  'Februari',
  'Maret',
  'April',
  'Mei',
  'Juni',
  'Juli',
  'Agustus',
  'September',
  'Oktober',
  'November',
  'Desember',
];

function formatDateInline(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Tidak ada';
  const match = ISO_DATE_RE.exec(dateStr.trim());
  if (!match) return dateStr;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const monthName = MONTHS_INDO[month - 1];
  return monthName ? `${day} ${monthName} ${year}` : dateStr;
}

function normalizeCategory(snapshot: TransactionSnapshot | null | undefined): string {
  const name = snapshot?.category_name?.trim();
  return name ? name : 'Tanpa kategori';
}

function normalizeOptionalText(value: string | null | undefined, emptyLabel = 'Kosong'): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : emptyLabel;
}

/**
 * Compute human-readable field diffs between `before` and `after` snapshots.
 * Never surfaces `source_key` or internal identifiers.
 */
export function describeHistoryChanges(entry: TransactionHistoryEntry): HistoryFieldChange[] {
  const { before, after } = entry;
  if (!after || entry.action === 'delete') {
    return [];
  }

  const changes: HistoryFieldChange[] = [];

  if (before.amount !== after.amount) {
    changes.push({
      field: 'amount',
      label: 'Nominal',
      before: formatRupiahInline(before.amount),
      after: formatRupiahInline(after.amount),
    });
  }

  const beforeCategory = normalizeCategory(before);
  const afterCategory = normalizeCategory(after);
  if (beforeCategory !== afterCategory || (before.category_id ?? null) !== (after.category_id ?? null)) {
    changes.push({
      field: 'category',
      label: 'Kategori',
      before: beforeCategory,
      after: afterCategory,
    });
  }

  if (before.transaction_date !== after.transaction_date) {
    changes.push({
      field: 'transaction_date',
      label: 'Tanggal',
      before: formatDateInline(before.transaction_date),
      after: formatDateInline(after.transaction_date),
    });
  }

  const beforeNote = (before.note ?? '').trim();
  const afterNote = (after.note ?? '').trim();
  if (beforeNote !== afterNote) {
    changes.push({
      field: 'note',
      label: 'Catatan',
      before: normalizeOptionalText(before.note),
      after: normalizeOptionalText(after.note),
    });
  }

  const beforeAsset = (before.asset_name ?? '').trim();
  const afterAsset = (after.asset_name ?? '').trim();
  if (beforeAsset !== afterAsset) {
    changes.push({
      field: 'asset_name',
      label: 'Aset',
      before: normalizeOptionalText(before.asset_name),
      after: normalizeOptionalText(after.asset_name),
    });
  }

  return changes;
}

/** Primary title for a snapshot row in history lists. */
export function snapshotPrimaryTitle(snapshot: TransactionSnapshot): string {
  const category = snapshot.category_name?.trim();
  if (category) return category;
  const asset = snapshot.asset_name?.trim();
  if (asset) return asset;
  return transactionTypeLabel(snapshot.type);
}

/** Deduplicate and merge history pages in newest-first order. */
export function mergeHistoryPages(
  existing: readonly TransactionHistoryEntry[],
  incoming: readonly TransactionHistoryEntry[]
): TransactionHistoryEntry[] {
  const seen = new Set<number>();
  const merged: TransactionHistoryEntry[] = [];

  for (const item of existing) {
    if (!seen.has(item.id)) {
      seen.add(item.id);
      merged.push(item);
    }
  }
  for (const item of incoming) {
    if (!seen.has(item.id)) {
      seen.add(item.id);
      merged.push(item);
    }
  }

  return merged;
}

function normalizeUtcIso(iso: string): string {
  const trimmed = String(iso ?? '').trim();
  if (!trimmed) return '';
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(trimmed)) {
    return trimmed;
  }
  return `${trimmed.replace(' ', 'T')}Z`;
}

function shortTimezoneLabel(timezone?: string | null): string {
  const tz = timezone?.trim();
  if (!tz) return 'waktu perangkat';
  if (tz === 'Asia/Jakarta') return 'WIB';
  if (tz === 'Asia/Makassar' || tz === 'Asia/Ujung_Pandang') return 'WITA';
  if (tz === 'Asia/Jayapura') return 'WIT';
  return tz;
}

/**
 * Format an ISO UTC timestamp using the user's IANA timezone when known, or
 * fall back to device-local time with an explicit label.
 */
export function formatAuditTimestamp(
  isoUtc: string,
  userTimezone?: string | null
): string {
  const normalized = normalizeUtcIso(isoUtc);
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return isoUtc || '';
  }

  const tz = userTimezone?.trim();
  if (tz) {
    try {
      const formatter = new Intl.DateTimeFormat('id-ID', {
        timeZone: tz,
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
      const formatted = formatter.format(date).replace(/\./g, ':');
      return `${formatted} (${shortTimezoneLabel(tz)})`;
    } catch {
      // Fall back to device-local formatting below when the runtime lacks IANA tz support.
    }
  }

  const day = date.getDate();
  const month = MONTHS_INDO[date.getMonth()]?.slice(0, 3) ?? '';
  const year = date.getFullYear();
  const hours = `${date.getHours()}`.padStart(2, '0');
  const minutes = `${date.getMinutes()}`.padStart(2, '0');
  return `${day} ${month} ${year}, ${hours}:${minutes} (waktu perangkat)`;
}
