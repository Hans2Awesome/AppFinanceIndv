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
