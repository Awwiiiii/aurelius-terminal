/**
 * Market Overview API client methods.
 */

import { apiClient } from './client';
import type {
  BenchmarkSnapshot,
  MarketMoverItem,
  MarketOverviewSnapshot,
  MarketStatus,
} from '../types/overview';

/**
 * Fetch composite market overview snapshot with optional forced provider refresh.
 */
export async function fetchMarketOverview(
  forceRefresh: boolean = false
): Promise<MarketOverviewSnapshot> {
  const url = forceRefresh
    ? '/api/v1/market/overview?force_refresh=true'
    : '/api/v1/market/overview';
  return apiClient<MarketOverviewSnapshot>(url);
}

/**
 * Fetch canonical benchmarks snapshot list.
 */
export async function fetchBenchmarks(): Promise<BenchmarkSnapshot[]> {
  return apiClient<BenchmarkSnapshot[]>('/api/v1/market/benchmarks');
}

/**
 * Fetch ranked market movers for a category (GAINERS, LOSERS, ACTIVE).
 */
export async function fetchMarketMovers(
  category: 'GAINERS' | 'LOSERS' | 'ACTIVE' = 'GAINERS'
): Promise<MarketMoverItem[]> {
  return apiClient<MarketMoverItem[]>(
    `/api/v1/market/movers?category=${category}`
  );
}

/**
 * Fetch operational market session telemetry.
 */
export async function fetchMarketStatus(): Promise<MarketStatus> {
  return apiClient<MarketStatus>('/api/v1/market/status');
}
