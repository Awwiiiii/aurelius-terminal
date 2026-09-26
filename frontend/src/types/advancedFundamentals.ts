/**
 * frontend/src/types/advancedFundamentals.ts
 * ==========================================
 * Strongly typed TypeScript interfaces for M7B.2 Advanced Fundamental Analysis:
 * ROIC/NOPAT, 3-Step and 5-Step DuPont decompositions, Quality Diagnostics (Sloan & OQR),
 * Common-Size Financial Statements, Multi-Period Fundamental Trends, and Calendar-Time CAGR.
 */

import type { FinancialPeriodSchema } from './financials';

export type AdvancedPeriodType = 'ANNUAL' | 'QUARTERLY' | 'TTM';

export interface MetricDiagnosticSchema {
  code: string;
  message: string;
  details: Record<string, string>;
}

export interface MetricProvenanceSchema {
  formula_id: string;
  methodology_version: string;
  source_fact_ids: string[];
  source_concepts: string[];
  source_periods: string[];
  provider: string;
  methodology_notes?: string | null;
}

export interface MetricValueResponse {
  metric_id: string;
  category: string;
  status: 'VALID' | 'UNAVAILABLE' | 'DISTORTED' | 'NOT_APPLICABLE' | string;
  value?: string | number | null;
  formatted_value: string;
  unit: 'PERCENT' | 'RATIO' | 'CURRENCY' | 'DAYS' | string;
  currency?: string | null;
  period_key: string;
  is_derived: boolean;
  diagnostics: MetricDiagnosticSchema[];
  provenance: MetricProvenanceSchema;
}

export interface DuPontReconciliation {
  is_reconciled: boolean;
  reconciliation_discrepancy?: string | number | null;
}

export interface DuPont3StepResponse {
  net_profit_margin: MetricValueResponse;
  asset_turnover: MetricValueResponse;
  equity_multiplier: MetricValueResponse;
  reconstructed_roe: MetricValueResponse;
  direct_roe: MetricValueResponse;
  is_reconciled: boolean;
  reconciliation_discrepancy?: string | number | null;
  reconciliation?: DuPontReconciliation | null;
}

export interface DuPont5StepResponse {
  tax_burden: MetricValueResponse;
  interest_burden: MetricValueResponse;
  ebit_margin: MetricValueResponse;
  asset_turnover: MetricValueResponse;
  equity_multiplier: MetricValueResponse;
  reconstructed_roe: MetricValueResponse;
  direct_roe: MetricValueResponse;
  is_reconciled: boolean;
  reconciliation_discrepancy?: string | number | null;
  reconciliation?: DuPontReconciliation | null;
}

export interface QualityDiagnosticsResponse {
  sloan_accruals: MetricValueResponse;
  operating_quality_ratio: MetricValueResponse;
  diagnostics_summary: MetricDiagnosticSchema[];
}

export interface AdvancedFundamentalsResponse {
  ticker: string;
  period_type: AdvancedPeriodType;
  period: FinancialPeriodSchema;
  reporting_currency?: string | null;
  effective_tax_rate: MetricValueResponse;
  nopat: MetricValueResponse;
  invested_capital: MetricValueResponse;
  average_invested_capital: MetricValueResponse;
  roic: MetricValueResponse;
  dupont_3step: DuPont3StepResponse;
  dupont_5step: DuPont5StepResponse;
  quality_diagnostics: QualityDiagnosticsResponse;
  diagnostics_summary: MetricDiagnosticSchema[];
  provenance?: MetricProvenanceSchema | null;
}

export interface CommonSizeItemSchema {
  concept_name: string;
  reported_value?: string | number | null;
  common_size_percent?: string | number | null;
  status: string;
  diagnostics: MetricDiagnosticSchema[];
  provenance: MetricProvenanceSchema;
}

export interface CommonSizeTableSchema {
  statement_type: 'INCOME_STATEMENT' | 'BALANCE_SHEET' | 'CASH_FLOW' | string;
  period: FinancialPeriodSchema;
  display_title: string;
  base_concept_name: string;
  base_value?: string | number | null;
  status: string;
  items: CommonSizeItemSchema[];
  diagnostics: MetricDiagnosticSchema[];
  provenance: MetricProvenanceSchema;
}

export interface CommonSizeStatementsResponse {
  ticker: string;
  period_type: AdvancedPeriodType;
  income_statement: CommonSizeTableSchema;
  balance_sheet: CommonSizeTableSchema;
  cash_flow_statement: CommonSizeTableSchema;
  period?: FinancialPeriodSchema | null;
  provenance?: MetricProvenanceSchema | null;
}

export interface TrendDataPointSchema {
  period: FinancialPeriodSchema;
  value?: string | number | null;
  formatted_value: string;
  status: string;
  qoq_change?: string | number | null;
  yoy_change?: string | number | null;
  ttm_sequential_change?: string | number | null;
  diagnostics: MetricDiagnosticSchema[];
  provenance: MetricProvenanceSchema;
}

export interface MetricTrendSeriesSchema {
  metric_name: string;
  unit: string;
  points: TrendDataPointSchema[];
}

export interface CAGRDataPointSchema {
  metric_name: string;
  horizon: '3Y' | '5Y';
  cagr?: string | number | null;
  formatted_cagr: string;
  status: string;
  start_period: FinancialPeriodSchema;
  end_period: FinancialPeriodSchema;
  calendar_days: number;
  diagnostics: MetricDiagnosticSchema[];
  provenance: MetricProvenanceSchema;
}

export interface FundamentalTrendsResponse {
  ticker: string;
  period_type: AdvancedPeriodType;
  series: Record<string, MetricTrendSeriesSchema>;
  cagr_results: Record<string, CAGRDataPointSchema[]>;
  provenance?: MetricProvenanceSchema | null;
}

/**
 * Standard audit modal target payload
 */
export interface ProvenanceAuditTarget {
  metricName: string;
  formattedValue: string;
  periodLabel: string;
  status: string;
  category?: string;
  unit?: string;
  currency?: string | null;
  isDerived?: boolean;
  provenance: MetricProvenanceSchema;
  diagnostics?: MetricDiagnosticSchema[];
  allowFallbackUsed?: boolean;
}
