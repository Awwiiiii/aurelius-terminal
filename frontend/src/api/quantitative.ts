/**
 * Quantitative Market Analytics API client services.
 */

import type { HistoricalTimeHorizon } from '../types/historical';
import type {
  MultiAssetCorrelationMatrixResponse,
  QuantitativeMetricType,
  ReturnCalculationType,
  ReturnDistributionSummaryResponse,
  RollingQuantitativeSeriesResponse,
} from '../types/quantitative';
import { apiClient } from './client';

export interface QuantitativeFilterOptions {
  customStart?: string;
  customEnd?: string;
  forceRefresh?: boolean;
}

/**
 * Fetch empirical return distribution summary for a single security.
 */
export async function fetchReturnDistribution(
  ticker: string,
  horizon: HistoricalTimeHorizon = '1Y',
  returnType: ReturnCalculationType = 'SIMPLE',
  options: QuantitativeFilterOptions = {}
): Promise<ReturnDistributionSummaryResponse> {
  const cleanTicker = encodeURIComponent(ticker.trim().toUpperCase());
  const params = new URLSearchParams();
  params.append('horizon', horizon);
  params.append('return_type', returnType);

  if (options.customStart) {
    params.append('custom_start', options.customStart);
  }
  if (options.customEnd) {
    params.append('custom_end', options.customEnd);
  }
  if (options.forceRefresh) {
    params.append('force_refresh', 'true');
  }

  return apiClient<ReturnDistributionSummaryResponse>(
    `/api/v1/analytics/distribution/${cleanTicker}?${params.toString()}`
  );
}

/**
 * Compare a multi-asset universe with inner date alignment.
 */
export async function fetchAssetComparison(
  tickers: string[],
  horizon: HistoricalTimeHorizon = '1Y',
  options: QuantitativeFilterOptions = {}
): Promise<MultiAssetCorrelationMatrixResponse> {
  const params = new URLSearchParams();
  params.append('tickers', tickers.join(','));
  params.append('horizon', horizon);

  if (options.customStart) {
    params.append('custom_start', options.customStart);
  }
  if (options.customEnd) {
    params.append('custom_end', options.customEnd);
  }
  if (options.forceRefresh) {
    params.append('force_refresh', 'true');
  }

  return apiClient<MultiAssetCorrelationMatrixResponse>(
    `/api/v1/analytics/compare?${params.toString()}`
  );
}

/**
 * Fetch sliding window rolling quantitative time series.
 */
export async function fetchRollingSeries(
  tickerA: string,
  metric: QuantitativeMetricType = 'VOLATILITY',
  window: number = 20,
  tickerB?: string,
  horizon: HistoricalTimeHorizon = '1Y',
  options: QuantitativeFilterOptions = {}
): Promise<RollingQuantitativeSeriesResponse> {
  const params = new URLSearchParams();
  params.append('ticker_a', tickerA.trim().toUpperCase());
  params.append('metric', metric);
  params.append('window', String(window));
  params.append('horizon', horizon);

  if (tickerB && metric === 'CORRELATION') {
    params.append('ticker_b', tickerB.trim().toUpperCase());
  }
  if (options.customStart) {
    params.append('custom_start', options.customStart);
  }
  if (options.customEnd) {
    params.append('custom_end', options.customEnd);
  }
  if (options.forceRefresh) {
    params.append('force_refresh', 'true');
  }

  return apiClient<RollingQuantitativeSeriesResponse>(
    `/api/v1/analytics/rolling?${params.toString()}`
  );
}
