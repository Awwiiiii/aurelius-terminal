/**
 * frontend/src/api/fundamental.ts
 * ===============================
 * Client API for fundamental analysis and financial ratios endpoints.
 */

import type { FiscalPeriodType } from '../types/financials';
import type { FundamentalReportResponse } from '../types/fundamental';
import { apiClient } from './client';

/**
 * Fetch fundamental analysis report containing metrics across all periods.
 */
export async function fetchFundamentalReport(
  ticker: string,
  frequency: FiscalPeriodType = 'ANNUAL',
  allowPointInTimeFallback: boolean = false
): Promise<FundamentalReportResponse> {
  const cleanTicker = encodeURIComponent(ticker.trim().toUpperCase());
  return apiClient<FundamentalReportResponse>(
    `/api/v1/market/financials/${cleanTicker}/fundamentals?frequency=${frequency}&allow_point_in_time_fallback=${allowPointInTimeFallback}`
  );
}
