/**
 * frontend/src/types/fundamental.ts
 * =================================
 * TypeScript types for AURELIUS fundamental analysis metrics,
 * diagnostics, auditable provenance, and report responses.
 */

import type { FinancialPeriodSchema, FiscalPeriodType } from './financials';

export type MetricCategory =
  | 'GROWTH'
  | 'PROFITABILITY'
  | 'LIQUIDITY'
  | 'SOLVENCY'
  | 'EFFICIENCY'
  | 'CASH_FLOW';

export type MetricStatus =
  | 'VALID'
  | 'UNAVAILABLE'
  | 'NOT_APPLICABLE'
  | 'DISTORTED';

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

export interface MetricResultSchema {
  metric_id: string;
  category: MetricCategory;
  status: MetricStatus;
  value?: number | null;
  formatted_value: string;
  unit: string;
  currency?: string | null;
  period_key: string;
  is_derived: boolean;
  diagnostics: MetricDiagnosticSchema[];
  provenance: MetricProvenanceSchema;
}

export interface FundamentalReportResponse {
  ticker: string;
  frequency: FiscalPeriodType;
  reporting_currency?: string | null;
  periods: FinancialPeriodSchema[];
  metrics: Record<string, MetricResultSchema[]>;
  diagnostics_summary: MetricDiagnosticSchema[];
}
