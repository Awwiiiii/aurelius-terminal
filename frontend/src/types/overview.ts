/**
 * Market Overview TypeScript definitions matching backend API contracts.
 */

export type MarketSessionState =
  | 'REGULAR_OPEN'
  | 'PRE_MARKET'
  | 'AFTER_HOURS'
  | 'CLOSED'
  | 'WEEKEND'
  | 'UNKNOWN';

export type DataFreshness = 'REAL_TIME' | 'DELAYED' | 'STALE' | 'UNKNOWN';

export interface BenchmarkSnapshot {
  benchmark_id: string;
  name: string;
  category: string;
  provider_ticker: string;
  price: string;
  change: string;
  change_percent: string;
  previous_close: string | null;
  day_high: string | null;
  day_low: string | null;
  currency: string;
  is_currency_priced: boolean;
  provider: string;
  timestamp: string;
}

export interface MarketMoverItem {
  ticker: string;
  name: string;
  price: string;
  change: string;
  change_percent: string;
  previous_close: string | null;
  volume: number | null;
  market_cap: string | null;
  exchange: string | null;
  category: 'GAINERS' | 'LOSERS' | 'ACTIVE';
}

export interface MarketStatus {
  region: string;
  session_state: MarketSessionState;
  exchange_timezone: string;
  session_message: string | null;
  next_open: string | null;
  next_close: string | null;
  is_indicative: boolean;
}

export interface MarketOverviewSnapshot {
  market_status: MarketStatus;
  benchmarks: BenchmarkSnapshot[];
  gainers: MarketMoverItem[];
  losers: MarketMoverItem[];
  active: MarketMoverItem[];
  fetched_at: string;
  freshness: DataFreshness;
  cached: boolean;
  provider: string;
}
