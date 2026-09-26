/**
 * frontend/src/api/advancedFundamentals.ts
 * =========================================
 * Client API services for M7B.2 Advanced Fundamentals endpoints:
 * - Advanced Fundamentals (ROIC, NOPAT, DuPont, Quality Diagnostics)
 * - Common-Size Financial Statements (Income Statement, Balance Sheet, Cash Flow)
 * - Multi-Period Fundamental Trends & M4 Calendar-Time CAGR
 */

import type {
  AdvancedFundamentalsResponse,
  AdvancedPeriodType,
  CommonSizeStatementsResponse,
  FundamentalTrendsResponse,
} from '../types/advancedFundamentals';
import { apiClient } from './client';

/**
 * Fetch Advanced Fundamentals dossier:
 * ROIC, NOPAT, Invested Capital, 3-Step DuPont, 5-Step DuPont, and Quality Diagnostics.
 */
export async function fetchAdvancedFundamentals(
  ticker: string,
  periodType: AdvancedPeriodType = 'TTM',
  fiscalYear?: number | null,
  fiscalPeriod?: string | null,
  allowPointInTime: boolean = false
): Promise<AdvancedFundamentalsResponse> {
  const cleanTicker = encodeURIComponent(ticker.trim().toUpperCase());
  const params = new URLSearchParams({
    period_type: periodType,
    allow_point_in_time: String(allowPointInTime),
  });

  if (fiscalYear !== undefined && fiscalYear !== null) {
    params.set('fiscal_year', String(fiscalYear));
  }
  if (fiscalPeriod !== undefined && fiscalPeriod !== null && fiscalPeriod !== '') {
    params.set('fiscal_period', fiscalPeriod);
  }

  return apiClient<AdvancedFundamentalsResponse>(
    `/api/v1/financials/${cleanTicker}/advanced-fundamentals?${params.toString()}`
  );
}

/**
 * Fetch Common-Size Financial Statements:
 * Income Statement (% Revenue), Balance Sheet (% Assets), Cash Flow (% Revenue).
 */
export async function fetchCommonSizeStatements(
  ticker: string,
  periodType: AdvancedPeriodType = 'ANNUAL',
  fiscalYear?: number | null,
  fiscalPeriod?: string | null
): Promise<CommonSizeStatementsResponse> {
  const cleanTicker = encodeURIComponent(ticker.trim().toUpperCase());
  const params = new URLSearchParams({
    period_type: periodType,
  });

  if (fiscalYear !== undefined && fiscalYear !== null) {
    params.set('fiscal_year', String(fiscalYear));
  }
  if (fiscalPeriod !== undefined && fiscalPeriod !== null && fiscalPeriod !== '') {
    params.set('fiscal_period', fiscalPeriod);
  }

  return apiClient<CommonSizeStatementsResponse>(
    `/api/v1/financials/${cleanTicker}/common-size?${params.toString()}`
  );
}

/**
 * Fetch Multi-Period Fundamental Trends & M4 Calendar-Time CAGR.
 */
export async function fetchFundamentalTrends(
  ticker: string,
  periodType: AdvancedPeriodType = 'ANNUAL',
  metrics?: string[],
  limit: number = 20
): Promise<FundamentalTrendsResponse> {
  const cleanTicker = encodeURIComponent(ticker.trim().toUpperCase());
  const params = new URLSearchParams({
    period_type: periodType,
    limit: String(limit),
  });

  if (metrics && metrics.length > 0) {
    for (const m of metrics) {
      params.append('metrics', m);
    }
  }

  return apiClient<FundamentalTrendsResponse>(
    `/api/v1/financials/${cleanTicker}/fundamental-trends?${params.toString()}`
  );
}
