/**
 * Formatting helpers for financial quantities and timestamps.
 */

export function formatPrice(
  price: string | number | null | undefined,
  _currency: string = 'USD'
): string {
  if (price === null || price === undefined || price === '') {
    return '—';
  }
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (isNaN(num)) {
    return String(price);
  }
  // If price has more than 2 decimal places and is small, show up to 4 places, otherwise 2
  const decimals = num < 1 ? 4 : 2;
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: decimals,
  }).format(num);
}

export function formatChange(
  change: string | null | undefined,
  changePercent: string | null | undefined
): { text: string; isPositive: boolean; isNegative: boolean } {
  if (!change && !changePercent) {
    return { text: '—', isPositive: false, isNegative: false };
  }

  const changeNum = change ? parseFloat(change) : 0;
  const pctNum = changePercent ? parseFloat(changePercent) : 0;

  const isPositive = changeNum > 0 || pctNum > 0;
  const isNegative = changeNum < 0 || pctNum < 0;

  const sign = isPositive ? '+' : '';
  const changeFormatted = changeNum ? `${sign}${changeNum.toFixed(2)}` : '0.00';
  const pctFormatted = pctNum ? `${sign}${pctNum.toFixed(2)}%` : '0.00%';

  return {
    text: `${changeFormatted} (${pctFormatted})`,
    isPositive,
    isNegative,
  };
}

export function formatVolume(volume: number | null | undefined): string {
  if (volume === null || volume === undefined) {
    return '—';
  }
  return new Intl.NumberFormat('en-US').format(Math.round(volume));
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return '—';
  return dateStr;
}
