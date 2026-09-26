import React, { useCallback, useEffect, useState } from 'react';
import { fetchFundamentalReport } from '../../api/fundamental';
import type { FiscalPeriodType } from '../../types/financials';
import type {
  FundamentalReportResponse,
  MetricResultSchema,
} from '../../types/fundamental';
import { ErrorMessage } from '../ui/ErrorMessage';
import { TickerInput } from '../ui/TickerInput';
import { AdvancedFundamentalsWorkspace } from './AdvancedFundamentalsWorkspace';
import {
  MetricCategorySection,
  type MetricDefinition,
} from './MetricCategorySection';
import { ProvenanceModal } from './ProvenanceModal';

interface Props {
  initialTicker?: string;
  onSelectTicker?: (ticker: string) => void;
  onLaunchFinancials?: (ticker: string) => void;
}

const GROWTH_METRICS: MetricDefinition[] = [
  {
    id: 'REVENUE_GROWTH_YOY',
    label: 'Revenue Growth (YoY)',
    formulaDescription: '(Revenue_t - Revenue_{t-1}) / |Revenue_{t-1}|',
    unit: '%',
  },
  {
    id: 'REVENUE_GROWTH_QOQ',
    label: 'Revenue Growth (QoQ)',
    formulaDescription: '(Revenue_t - Revenue_{t-1}) / |Revenue_{t-1}| (Quarterly only)',
    unit: '%',
  },
];

const PROFITABILITY_METRICS: MetricDefinition[] = [
  {
    id: 'GROSS_PROFIT',
    label: 'Gross Profit',
    formulaDescription: 'Revenue - Cost of Revenue',
  },
  {
    id: 'GROSS_PROFIT_MARGIN',
    label: 'Gross Margin',
    formulaDescription: 'Gross Profit / Revenue',
    unit: '%',
  },
  {
    id: 'OPERATING_INCOME',
    label: 'Operating Income (EBIT)',
    formulaDescription: 'Reported Operating Income / EBIT',
  },
  {
    id: 'OPERATING_MARGIN',
    label: 'Operating Margin',
    formulaDescription: 'Operating Income / Revenue',
    unit: '%',
  },
  {
    id: 'NET_INCOME',
    label: 'Net Income',
    formulaDescription: 'Reported Consolidated Net Income',
  },
  {
    id: 'NET_PROFIT_MARGIN',
    label: 'Net Profit Margin',
    formulaDescription: 'Net Income / Revenue',
    unit: '%',
  },
  {
    id: 'RETURN_ON_ASSETS',
    label: 'Return on Assets (ROA)',
    formulaDescription: 'Net Income / Average Total Assets (Two-Point)',
    unit: '%',
  },
  {
    id: 'RETURN_ON_EQUITY',
    label: 'Return on Equity (ROE)',
    formulaDescription: 'Net Income / Average Stockholders Equity (Two-Point)',
    unit: '%',
  },
  {
    id: 'EBITDA_MARGIN',
    label: 'EBITDA Margin',
    formulaDescription: 'Reported EBITDA / Revenue',
    unit: '%',
  },
];

const LIQUIDITY_METRICS: MetricDefinition[] = [
  {
    id: 'WORKING_CAPITAL',
    label: 'Working Capital',
    formulaDescription: 'Current Assets - Current Liabilities',
  },
  {
    id: 'CURRENT_RATIO',
    label: 'Current Ratio',
    formulaDescription: 'Current Assets / Current Liabilities',
    unit: 'x',
  },
  {
    id: 'QUICK_RATIO',
    label: 'Quick Ratio (Acid Test)',
    formulaDescription: '(Cash + Marketable Securities + Receivables) / Current Liabilities',
    unit: 'x',
  },
  {
    id: 'CASH_RATIO',
    label: 'Cash Ratio',
    formulaDescription: 'Cash & Cash Equivalents / Current Liabilities',
    unit: 'x',
  },
];

const SOLVENCY_METRICS: MetricDefinition[] = [
  {
    id: 'GROSS_DEBT',
    label: 'Gross Funded Debt',
    formulaDescription: 'ST Debt + LT Debt (Canonical 5-tier Hierarchy)',
  },
  {
    id: 'NET_DEBT',
    label: 'Net Debt',
    formulaDescription: 'Gross Debt - Cash & Cash Equivalents',
  },
  {
    id: 'DEBT_TO_EQUITY',
    label: 'Debt-to-Equity (D/E)',
    formulaDescription: 'Gross Debt / Stockholders Equity',
    unit: 'x',
  },
  {
    id: 'DEBT_TO_ASSETS',
    label: 'Debt-to-Assets',
    formulaDescription: 'Gross Debt / Total Assets',
    unit: 'x',
  },
  {
    id: 'INTEREST_COVERAGE',
    label: 'Interest Coverage',
    formulaDescription: 'Operating Income (EBIT) / Interest Expense',
    unit: 'x',
  },
  {
    id: 'DEBT_TO_EBITDA',
    label: 'Debt-to-EBITDA',
    formulaDescription: 'Gross Debt / Reported EBITDA',
    unit: 'x',
  },
  {
    id: 'NET_DEBT_TO_EBITDA',
    label: 'Net Debt-to-EBITDA',
    formulaDescription: 'Net Debt / Reported EBITDA',
    unit: 'x',
  },
];

const EFFICIENCY_METRICS: MetricDefinition[] = [
  {
    id: 'ASSET_TURNOVER',
    label: 'Asset Turnover',
    formulaDescription: 'Revenue / Average Total Assets',
    unit: 'x',
  },
  {
    id: 'RECEIVABLES_TURNOVER',
    label: 'Receivables Turnover',
    formulaDescription: 'Revenue / Average Accounts Receivable',
    unit: 'x',
  },
  {
    id: 'INVENTORY_TURNOVER',
    label: 'Inventory Turnover',
    formulaDescription: 'Cost of Revenue / Average Inventory',
    unit: 'x',
  },
  {
    id: 'PAYABLES_TURNOVER',
    label: 'Payables Turnover',
    formulaDescription: 'Cost of Revenue / Average Accounts Payable',
    unit: 'x',
  },
  {
    id: 'DAYS_SALES_OUTSTANDING',
    label: 'Days Sales Outstanding (DSO)',
    formulaDescription: 'Avg AR / Revenue × Exact Duration Days',
    unit: 'days',
  },
  {
    id: 'DAYS_INVENTORY_OUTSTANDING',
    label: 'Days Inventory Outstanding (DIO)',
    formulaDescription: 'Avg Inventory / Cost of Revenue × Exact Duration Days',
    unit: 'days',
  },
  {
    id: 'DAYS_PAYABLE_OUTSTANDING',
    label: 'Days Payable Outstanding (DPO)',
    formulaDescription: 'Avg Accounts Payable / Cost of Revenue × Exact Duration Days',
    unit: 'days',
  },
  {
    id: 'CASH_CONVERSION_CYCLE',
    label: 'Cash Conversion Cycle (CCC)',
    formulaDescription: 'DIO + DSO - DPO',
    unit: 'days',
  },
];

const CASH_FLOW_METRICS: MetricDefinition[] = [
  {
    id: 'OPERATING_CASH_FLOW',
    label: 'Operating Cash Flow (CFO)',
    formulaDescription: 'Reported Cash Flow from Operations',
  },
  {
    id: 'CAPITAL_EXPENDITURES',
    label: 'Capital Expenditures (CapEx)',
    formulaDescription: 'Reported Capital Outlay for Property, Plant & Equipment',
  },
  {
    id: 'FREE_CASH_FLOW',
    label: 'Free Cash Flow (FCF)',
    formulaDescription: 'Operating Cash Flow - Capital Expenditures',
  },
  {
    id: 'FCF_MARGIN',
    label: 'FCF Margin',
    formulaDescription: 'Free Cash Flow / Revenue',
    unit: '%',
  },
  {
    id: 'FCF_CONVERSION',
    label: 'FCF Conversion Rate',
    formulaDescription: 'Free Cash Flow / Net Income',
    unit: '%',
  },
  {
    id: 'CFO_TO_NET_INCOME',
    label: 'CFO-to-Net Income Quality',
    formulaDescription: 'Operating Cash Flow / Net Income',
    unit: 'x',
  },
];

export const FundamentalAnalysisView: React.FC<Props> = ({
  initialTicker = 'AAPL',
  onSelectTicker,
  onLaunchFinancials,
}) => {
  const [ticker, setTicker] = useState<string>(initialTicker);
  const [workspaceSection, setWorkspaceSection] = useState<'CORE_RATIOS' | 'ADVANCED'>('ADVANCED');
  const [frequency, setFrequency] = useState<FiscalPeriodType>('ANNUAL');
  const [allowFallback, setAllowFallback] = useState<boolean>(false);
  const [report, setReport] = useState<FundamentalReportResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  // Provenance modal state
  const [selectedMetric, setSelectedMetric] = useState<{
    metric: MetricResultSchema;
    label: string;
  } | null>(null);

  const loadData = useCallback(
    async (sym: string, freq: FiscalPeriodType, fallback: boolean) => {
      setIsLoading(true);
      setError(null);

      try {
        const res = await fetchFundamentalReport(sym, freq, fallback);
        setReport(res);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setReport(null);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (workspaceSection === 'CORE_RATIOS') {
      loadData(ticker, frequency, allowFallback);
    }
  }, [ticker, frequency, allowFallback, workspaceSection, loadData]);

  const handleSelectTicker = (newTicker: string) => {
    const clean = newTicker.trim().toUpperCase();
    setTicker(clean);
    if (onSelectTicker) {
      onSelectTicker(clean);
    }
  };

  const handleInspectMetric = (metric: MetricResultSchema, label: string) => {
    setSelectedMetric({ metric, label });
  };

  return (
    <div className="fundamental-view-layout">
      {/* Top Workspace Header Bar */}
      <div className="fundamental-workspace-tabs-bar">
        <div className="workspace-tab-left">
          <span className="workspace-title-badge">FUNDAMENTAL ANALYSIS</span>
          <div className="workspace-tab-buttons">
            <button
              type="button"
              id="tab-core-ratios"
              className={`workspace-tab-btn ${workspaceSection === 'CORE_RATIOS' ? 'active' : ''}`}
              onClick={() => setWorkspaceSection('CORE_RATIOS')}
            >
              Overview / Core Ratios
            </button>
            <button
              type="button"
              id="tab-advanced-analytics"
              className={`workspace-tab-btn ${workspaceSection === 'ADVANCED' ? 'active' : ''}`}
              onClick={() => setWorkspaceSection('ADVANCED')}
            >
              Advanced Analytics
            </button>
            <button
              type="button"
              id="tab-financial-statements"
              className="workspace-tab-btn"
              onClick={() => {
                if (onLaunchFinancials) {
                  onLaunchFinancials(ticker);
                }
              }}
            >
              Financial Statements ↗
            </button>
          </div>
        </div>

        <div className="workspace-tab-right">
          <TickerInput
            currentTicker={ticker}
            onSelectTicker={handleSelectTicker}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* RENDER ACTIVE WORKSPACE SECTION */}
      {workspaceSection === 'ADVANCED' ? (
        <AdvancedFundamentalsWorkspace ticker={ticker} />
      ) : (
        <>
          {/* M7A Header controls bar */}
          <div className="fundamental-header-panel">
            <div className="fundamental-controls-left">
              <span className="section-context-label">CANONICAL RATIO MATRIX:</span>
            </div>

            <div className="fundamental-controls-right">
              <div className="frequency-toggle-buttons">
                <button
                  type="button"
                  className={`freq-btn ${frequency === 'ANNUAL' ? 'active' : ''}`}
                  onClick={() => setFrequency('ANNUAL')}
                >
                  ANNUAL
                </button>
                <button
                  type="button"
                  className={`freq-btn ${frequency === 'QUARTERLY' ? 'active' : ''}`}
                  onClick={() => setFrequency('QUARTERLY')}
                >
                  QUARTERLY
                </button>
              </div>

              <label
                className="fallback-toggle-label"
                title="Enable point-in-time denominator fallback when prior balance sheet is unavailable"
              >
                <input
                  type="checkbox"
                  className="fallback-checkbox"
                  checked={allowFallback}
                  onChange={(e) => setAllowFallback(e.target.checked)}
                />
                <span className="fallback-text">POINT-IN-TIME FALLBACK</span>
              </label>
            </div>
          </div>

          {/* Institutional Methodology Bar */}
          <div className="methodology-callout fundamental-methodology-banner">
            <div className="callout-title">
              <span className="callout-icon">◈</span>
              <span>INSTITUTIONAL METHODOLOGY ENGINE (M7A)</span>
            </div>
            <div className="callout-list">
              <div>
                • <strong>Strict Two-Point Average:</strong> Flow/balance ratios (ROA, ROE, Turnovers, Days metrics) enforce authoritative two-point balance sheet averaging <code>(t + t-1) / 2</code> across strictly consecutive periods.
              </div>
              <div>
                • <strong>Frequency-Aware Duration:</strong> Efficiency days metrics (DSO, DIO, DPO) compute exact calendar duration days <code>(end_date - start_date) + 1</code> rather than static 365-day approximations.
              </div>
              <div>
                • <strong>Canonical Gross Debt:</strong> Evaluates explicit funded debt components (ST + LT) with audited fallback hierarchy; non-debt liabilities are strictly excluded.
              </div>
            </div>
          </div>

          {error && (
            <ErrorMessage
              error={error}
              onRetry={() => loadData(ticker, frequency, allowFallback)}
            />
          )}

          {isLoading && (
            <div className="financials-loading-state">
              <span className="loading-spinner">◈</span>
              COMPUTING {frequency} CANONICAL FINANCIAL RATIOS FOR {ticker}...
            </div>
          )}

          {!isLoading && !error && report && report.periods.length === 0 && (
            <div className="financials-empty-state">
              <span className="empty-icon">▤</span>
              <div className="empty-title">NO FINANCIAL STATEMENTS AVAILABLE</div>
              <div className="empty-desc">
                No income statement, balance sheet, or cash flow filings were discovered for {ticker} under {frequency} frequency.
              </div>
            </div>
          )}

          {!isLoading && !error && report && report.periods.length > 0 && (
            <div className="fundamental-content-container">
              {/* Quick jump navigation */}
              <div className="category-jump-nav">
                <a href="#category-growth" className="jump-link">GROWTH</a>
                <a href="#category-profitability" className="jump-link">PROFITABILITY</a>
                <a href="#category-liquidity" className="jump-link">LIQUIDITY</a>
                <a href="#category-solvency" className="jump-link">SOLVENCY</a>
                <a href="#category-efficiency" className="jump-link">EFFICIENCY</a>
                <a href="#category-cash_flow" className="jump-link">CASH FLOW</a>
              </div>

              {/* 1. Growth */}
              <MetricCategorySection
                category="GROWTH"
                title="Revenue & Growth Dynamics"
                description="Normalized top-line expansion dynamics across consecutive annual and quarterly reporting periods."
                metricDefs={GROWTH_METRICS}
                periods={report.periods}
                metrics={report.metrics}
                onInspectMetric={handleInspectMetric}
              />

              {/* 2. Profitability */}
              <MetricCategorySection
                category="PROFITABILITY"
                title="Profitability & Returns on Capital"
                description="Multi-tier operating margins and canonical two-point capital productivity returns (ROA, ROE)."
                metricDefs={PROFITABILITY_METRICS}
                periods={report.periods}
                metrics={report.metrics}
                onInspectMetric={handleInspectMetric}
              />

              {/* 3. Liquidity */}
              <MetricCategorySection
                category="LIQUIDITY"
                title="Short-Term Liquidity & Capital Coverage"
                description="Classified working capital buffers, current ratios, and immediate cash availability metrics."
                metricDefs={LIQUIDITY_METRICS}
                periods={report.periods}
                metrics={report.metrics}
                onInspectMetric={handleInspectMetric}
              />

              {/* 4. Solvency */}
              <MetricCategorySection
                category="SOLVENCY"
                title="Long-Term Capital Structure & Solvency"
                description="Funded debt resolution, debt burdens, interest servicing coverage, and leverage capacity."
                metricDefs={SOLVENCY_METRICS}
                periods={report.periods}
                metrics={report.metrics}
                onInspectMetric={handleInspectMetric}
              />

              {/* 5. Efficiency */}
              <MetricCategorySection
                category="EFFICIENCY"
                title="Operating Efficiency & Working Capital Velocity"
                description="Exact period-day turnover rates, cash conversion cycles (CCC), and inventory/receivable cycles."
                metricDefs={EFFICIENCY_METRICS}
                periods={report.periods}
                metrics={report.metrics}
                onInspectMetric={handleInspectMetric}
              />

              {/* 6. Cash Flow */}
              <MetricCategorySection
                category="CASH_FLOW"
                title="Cash Flow Generation & Earnings Quality"
                description="Operating cash generation, capital reinvestment intensity, free cash flow (FCF), and CFO-to-net income conversion."
                metricDefs={CASH_FLOW_METRICS}
                periods={report.periods}
                metrics={report.metrics}
                onInspectMetric={handleInspectMetric}
              />
            </div>
          )}

          {/* Auditable Provenance Inspector Modal */}
          {selectedMetric && (
            <ProvenanceModal
              metric={selectedMetric.metric}
              metricLabel={selectedMetric.label}
              onClose={() => setSelectedMetric(null)}
            />
          )}
        </>
      )}
    </div>
  );
};
