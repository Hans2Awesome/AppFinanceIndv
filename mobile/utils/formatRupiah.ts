/**
 * Format number into Indonesian Rupiah currency string.
 */
export function formatRupiah(amount: number): string {
  if (isNaN(amount) || amount === null || amount === undefined) {
    return 'Rp0';
  }
  const formatted = Math.abs(Math.round(amount))
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return (amount < 0 ? '-Rp' : 'Rp') + formatted;
}

export function formatDateIndo(dateStr: string): string {
  if (!dateStr) return '';
  const months = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
  ];
  try {
    const [year, month, day] = dateStr.split('-').map(Number);
    return `${day} ${months[month - 1]} ${year}`;
  } catch {
    return dateStr;
  }
}

/**
 * Pick a display size for a money figure so it fits one line on a phone.
 * Deterministic instead of `adjustsFontSizeToFit`, which is iOS-only.
 */
export function amountFontSize(text: string, base = 44, floor = 24): number {
  const length = text.length;
  if (length <= 11) return base;
  if (length <= 14) return Math.round(base * 0.82);
  if (length <= 18) return Math.round(base * 0.66);
  return floor;
}
