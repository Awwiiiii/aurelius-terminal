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

export function formatMarketCap(
  marketCap: string | number | null | undefined
): string {
  if (marketCap === null || marketCap === undefined || marketCap === '') {
    return '—';
  }
  const cleanStr =
    typeof marketCap === 'string'
      ? marketCap.replace(/[$,]/g, '').trim()
      : marketCap;
  const num = typeof cleanStr === 'string' ? parseFloat(cleanStr) : cleanStr;
  if (isNaN(num)) {
    return String(marketCap);
  }
  const isNegative = num < 0;
  const abs = Math.abs(num);
  const sign = isNegative ? '-' : '';

  if (abs >= 1e12) {
    return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  }
  if (abs >= 1e9) {
    return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  }
  if (abs >= 1e6) {
    return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  }
  if (abs >= 1e3) {
    return `${sign}$${(abs / 1e3).toFixed(2)}K`;
  }
  return `${sign}$${new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(abs)}`;
}

/**
 * Display-only formatter for institutional financial values.
 * Preserves percentages, ratios, days, and formats large/small currency quantities
 * into canonical compact terminal notation ($112.28B, $135.05B, etc.).
 */
export function formatCompactFinancialValue(
  value: string | number | null | undefined,
  unit?: string
): string {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  const strVal = String(value).trim();
  if (strVal === '—' || strVal === 'UNAVAILABLE' || strVal === 'NOT_APPLICABLE') {
    return '—';
  }
  if (unit === 'PERCENT' || strVal.endsWith('%')) {
    return strVal;
  }
  if (unit === 'DAYS' || strVal.includes('days')) {
    return strVal;
  }
  if (unit === 'RATIO' || strVal.endsWith('x')) {
    return strVal;
  }
  return formatMarketCap(value);
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return '—';
  return dateStr;
}

