/**
 * frontend/src/types/financials.ts
 * =================================
 * TypeScript type definitions for AURELIUS financial statement infrastructure.
 */

export type StatementType = 'INCOME_STATEMENT' | 'BALANCE_SHEET' | 'CASH_FLOW';

export type FiscalPeriodType = 'ANNUAL' | 'QUARTERLY';

export type PeriodType = 'INSTANT' | 'DURATION';

export interface FinancialPeriodSchema {
  period_key: string;
  period_type: PeriodType;
  instant_date?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  fiscal_year?: number | null;
  fiscal_period?: string | null;
  is_period_label_source_reported: boolean;
  calendar_year?: number | null;
  display_label: string;
}

export interface FinancialMatrixRowSchema {
  concept_key: string;
  display_name: string;
  canonical_concept?: string | null;
  is_canonical: boolean;
  values_by_period: Record<string, string | number | null>;
}

export interface FinancialStatementMatrixResponse {
  company_id: string;
  statement_type: StatementType;
  frequency: FiscalPeriodType;
  currency?: string | null;
  periods: FinancialPeriodSchema[];
  rows: FinancialMatrixRowSchema[];
}
