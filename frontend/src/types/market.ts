/**
 * Market data TypeScript type definitions matching backend API contracts.
 */

export interface QuoteResponse {
  ticker: string;
  price: string;
  timestamp: string;
  currency: string;
  change: string | null;
  change_percent: string | null;
  volume: number | null;
  open: string | null;
  high: string | null;
  low: string | null;
  previous_close: string | null;
  market_state: string;
  provider: string;
  is_delayed: boolean;
}

export interface OHLCVBarResponse {
  timestamp: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: number;
  adj_close: string | null;
}

export interface OHLCVResponse {
  ticker: string;
  interval: string;
  bars: OHLCVBarResponse[];
  provider: string;
  is_adjusted: boolean;
}

export interface ApiErrorResponse {
  error: string;
  message: string;
  ticker?: string;
  check?: string;
  provider?: string;
}
