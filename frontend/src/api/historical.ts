/**
 * Historical Market Analysis API client services.
 */

import type {
  HistoricalAnalysisResponse,
  HistoricalTimeHorizon,
} from '../types/historical';
import { apiClient } from './client';

export interface HistoricalAnalysisOptions {
  startDate?: string;
  endDate?: string;
  benchmark?: string;
  includeBenchmark?: boolean;
  forceRefresh?: boolean;
}

/**
 * Fetch full historical analysis for a security over a specified horizon.
 */
export async function fetchHistoricalAnalysis(
  ticker: string,
  horizon: HistoricalTimeHorizon = '1Y',
  options: HistoricalAnalysisOptions = {}
): Promise<HistoricalAnalysisResponse> {
  const cleanTicker = encodeURIComponent(ticker.trim().toUpperCase());
  const params = new URLSearchParams();
  params.append('horizon', horizon);

  if (options.startDate) {
    params.append('start_date', options.startDate);
  }
  if (options.endDate) {
    params.append('end_date', options.endDate);
  }
  if (options.benchmark) {
    params.append('benchmark', options.benchmark);
  }
  if (options.includeBenchmark !== undefined) {
    params.append('include_benchmark', String(options.includeBenchmark));
  }
  if (options.forceRefresh) {
    params.append('force_refresh', 'true');
  }

  return apiClient<HistoricalAnalysisResponse>(
    `/api/v1/market/history/${cleanTicker}/analysis?${params.toString()}`
  );
}
