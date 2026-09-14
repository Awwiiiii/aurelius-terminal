/**
 * frontend/src/api/financials.ts
 * ===============================
 * Client API for financial statement endpoints.
 */

import type {
  FinancialStatementMatrixResponse,
  FiscalPeriodType,
  StatementType,
} from '../types/financials';
import { apiClient } from './client';

/**
 * Fetch multi-period financial statement presentation matrix.
 */
export async function fetchFinancialMatrix(
  ticker: string,
  statementType: StatementType = 'INCOME_STATEMENT',
  frequency: FiscalPeriodType = 'ANNUAL'
): Promise<FinancialStatementMatrixResponse> {
  const cleanTicker = encodeURIComponent(ticker.trim().toUpperCase());
  return apiClient<FinancialStatementMatrixResponse>(
    `/api/v1/market/financials/${cleanTicker}/matrix?statement_type=${statementType}&frequency=${frequency}`
  );
}
