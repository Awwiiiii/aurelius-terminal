/**
 * Market Data API client services.
 */

import type { OHLCVResponse, QuoteResponse } from '../types/market';
import { apiClient } from './client';

/**
 * Format a Date object as YYYY-MM-DD.
 */
export function formatDateISO(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Calculate explicit start and end dates for the last 30 calendar days.
 */
export function getLast30DaysRange(): { start: string; end: string } {
  const now = new Date();
  const past = new Date();
  past.setDate(now.getDate() - 30);
  return {
    start: formatDateISO(past),
    end: formatDateISO(now),
  };
}

/**
 * Fetch market quote snapshot for a ticker symbol.
 */
export async function fetchQuote(ticker: string): Promise<QuoteResponse> {
  const cleanTicker = encodeURIComponent(ticker.trim().toUpperCase());
  return apiClient<QuoteResponse>(`/api/v1/market/quote/${cleanTicker}`);
}

/**
 * Fetch historical OHLCV bars for a ticker symbol over explicit start and end dates.
 */
export async function fetchOHLCV(
  ticker: string,
  start: string,
  end: string,
  interval: string = '1d'
): Promise<OHLCVResponse> {
  const cleanTicker = encodeURIComponent(ticker.trim().toUpperCase());
  const params = new URLSearchParams({
    start,
    end,
    interval,
  });
  return apiClient<OHLCVResponse>(`/api/v1/market/ohlcv/${cleanTicker}?${params.toString()}`);
}

/**
 * Fetch last 30 days of OHLCV bars by calculating explicit start and end dates
 * and calling the existing API contract.
 */
export async function fetchLast30DaysOHLCV(ticker: string): Promise<OHLCVResponse> {
  const { start, end } = getLast30DaysRange();
  return fetchOHLCV(ticker, start, end, '1d');
}
