import React from 'react';
import type {
  AdvancedFundamentalsResponse,
  DuPont3StepResponse,
  DuPont5StepResponse,
  MetricValueResponse,
  ProvenanceAuditTarget,
} from '../../types/advancedFundamentals';
import type { MetricStatus } from '../../types/fundamental';
import { MetricStatusBadge } from './MetricStatusBadge';

interface Props {
  data: AdvancedFundamentalsResponse;
  allowFallback: boolean;
  onInspectProvenance: (target: ProvenanceAuditTarget) => void;
}

export const DupontAnalysisView: React.FC<Props> = ({
  data,
  allowFallback,
  onInspectProvenance,
}) => {
  const { dupont_3step, dupont_5step, period } = data;

  const renderFactorRow = (
    label: string,
    metric: MetricValueResponse,
    formulaDesc: string,
    categoryName: string
  ) => {
    const isUnavailable = metric.status === 'UNAVAILABLE';
    const isDistorted = metric.status === 'DISTORTED';
    const diag = metric.diagnostics && metric.diagnostics.length > 0
      ? metric.diagnostics[0]
      : null;

    return (
      <div className={`dupont-factor-row ${isUnavailable ? 'row-unavailable' : ''} ${isDistorted ? 'row-distorted' : ''}`}>
        <div className="factor-info">
          <div className="factor-label">{label}</div>
          <div className="factor-formula">{formulaDesc}</div>
        </div>

        <div className="factor-status-cell">
          <MetricStatusBadge
            status={metric.status as MetricStatus}
            diagnosticCount={metric.diagnostics.length}
          />
        </div>

        <div className="factor-value-cell">
          {isUnavailable ? (
            <div className="factor-unavailable-box">
              <span className="factor-unavailable-text">UNAVAILABLE</span>
              {diag && <span className="factor-reason" title={diag.message}>({diag.code})</span>}
            </div>
          ) : isDistorted ? (
            <div className="factor-distorted-box">
              <span className="factor-distorted-text">{metric.formatted_value}</span>
              {diag && <span className="factor-warning" title={diag.message}>⚠ {diag.message}</span>}
            </div>
          ) : (
            <span className="factor-valid-text">{metric.formatted_value}</span>
          )}
        </div>

        <div className="factor-action-cell">
          <button
            type="button"
            className="audit-inspect-btn-mini"
            onClick={() =>
              onInspectProvenance({
                metricName: `${label} (${categoryName})`,
                formattedValue: metric.formatted_value,
                periodLabel: period.display_label || period.period_key,
                status: metric.status,
                unit: metric.unit,
                currency: metric.currency,
                isDerived: metric.is_derived,
                provenance: metric.provenance,
                diagnostics: metric.diagnostics,
                category: 'DUPONT ROE DECOMPOSITION',
                allowFallbackUsed: allowFallback && metric.provenance.formula_id.includes('POINT_IN_TIME'),
              })
            }
          >
            PROVENANCE
          </button>
        </div>
      </div>
    );
  };

  const renderReconciliationHeader = (
    title: string,
    stepData: DuPont3StepResponse | DuPont5StepResponse,
    description: string
  ) => {
    const isReconciled = stepData.is_reconciled;
    const directRoe = stepData.direct_roe;
    const reconstructedRoe = stepData.reconstructed_roe;
    const isDistorted = reconstructedRoe.status === 'DISTORTED';
    const isUnavailable = reconstructedRoe.status === 'UNAVAILABLE';
    const primaryDiag = reconstructedRoe.diagnostics && reconstructedRoe.diagnostics.length > 0
      ? reconstructedRoe.diagnostics[0]
      : null;

    return (
      <div className="dupont-reconciliation-header">
        <div className="dupont-title-group">
          <h4 className="dupont-variant-title">{title}</h4>
          <span className="dupont-variant-desc">{description}</span>
        </div>

        <div className="dupont-roe-summary-box">
          <div className="roe-summary-item">
            <span className="roe-label">DIRECT ROE</span>
            <span className="roe-value">{directRoe.formatted_value}</span>
          </div>

          <div className="roe-math-operator">≈</div>

          <div className="roe-summary-item">
            <span className="roe-label">RECONSTRUCTED ROE</span>
            <span className="roe-value">{reconstructedRoe.formatted_value}</span>
          </div>

          <div className="reconciliation-badge-container">
            {isUnavailable ? (
              <span className="reconciliation-badge badge-unavailable">
                UNAVAILABLE
              </span>
            ) : isDistorted ? (
              <span className="reconciliation-badge badge-distorted" title={primaryDiag?.message}>
                DISTORTED
              </span>
            ) : isReconciled ? (
              <span className="reconciliation-badge badge-reconciled" title="Reconciled within tolerance 0.0001">
                ✓ RECONCILED (tol: 0.0001)
              </span>
            ) : (
              <span className="reconciliation-badge badge-discrepancy" title={`Discrepancy: ${stepData.reconciliation_discrepancy || 'exceeds tolerance'}`}>
                DISCREPANCY EXCEEDS TOLERANCE
              </span>
            )}
          </div>
        </div>

        {/* Edge State Callout if Distorted or Unavailable */}
        {(isDistorted || isUnavailable) && (
          <div className="dupont-edge-callout">
            <div className="edge-callout-header">
              <span className="edge-icon">⚠</span>
              <span className="edge-title">
                {title} {isDistorted ? 'Distorted' : 'Unavailable'}
              </span>
            </div>
            <div className="edge-callout-message">
              {primaryDiag?.message || 'Decomposition factors are mathematically distorted or denominators are non-positive.'}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="dupont-analysis-view">
      <div className="panel-section-header">
        <div>
          <div className="panel-badge">CAPITAL PRODUCTIVITY DECOMPOSITION</div>
          <h3 className="panel-title">DuPont ROE Framework (3-Step &amp; 5-Step)</h3>
        </div>
        <div className="period-indicator">
          {period.display_label || period.period_key} • Tolerance: 0.0001
        </div>
      </div>

      <div className="dupont-decompositions-container">
        {/* 3-Step DuPont Section */}
        <div className="dupont-variant-card">
          {renderReconciliationHeader(
            '3-Step DuPont Decomposition',
            dupont_3step,
            'Net Profit Margin × Asset Turnover × Equity Multiplier'
          )}

          <div className="dupont-factors-table">
            <div className="dupont-factors-header">
              <span className="col-factor">DECOMPOSITION FACTOR</span>
              <span className="col-status">STATUS</span>
              <span className="col-value">FACTOR VALUE</span>
              <span className="col-action">AUDIT</span>
            </div>
            {renderFactorRow(
              '1. Net Profit Margin',
              dupont_3step.net_profit_margin,
              'Net Income / Revenue',
              '3-Step DuPont'
            )}
            {renderFactorRow(
              '2. Asset Turnover',
              dupont_3step.asset_turnover,
              'Revenue / Average Total Assets',
              '3-Step DuPont'
            )}
            {renderFactorRow(
              '3. Equity Multiplier',
              dupont_3step.equity_multiplier,
              'Average Total Assets / Average Equity',
              '3-Step DuPont'
            )}
          </div>
        </div>

        {/* 5-Step DuPont Section */}
        <div className="dupont-variant-card">
          {renderReconciliationHeader(
            '5-Step Extended DuPont Decomposition',
            dupont_5step,
            'Tax Burden × Interest Burden × EBIT Margin × Asset Turnover × Equity Multiplier'
          )}

          <div className="dupont-factors-table">
            <div className="dupont-factors-header">
              <span className="col-factor">DECOMPOSITION FACTOR</span>
              <span className="col-status">STATUS</span>
              <span className="col-value">FACTOR VALUE</span>
              <span className="col-action">AUDIT</span>
            </div>
            {renderFactorRow(
              '1. Tax Burden',
              dupont_5step.tax_burden,
              'Net Income / EBT',
              '5-Step DuPont'
            )}
            {renderFactorRow(
              '2. Interest Burden',
              dupont_5step.interest_burden,
              'EBT / EBIT',
              '5-Step DuPont'
            )}
            {renderFactorRow(
              '3. Operating Margin (EBIT Margin)',
              dupont_5step.ebit_margin,
              'EBIT / Revenue',
              '5-Step DuPont'
            )}
            {renderFactorRow(
              '4. Asset Turnover',
              dupont_5step.asset_turnover,
              'Revenue / Average Total Assets',
              '5-Step DuPont'
            )}
            {renderFactorRow(
              '5. Equity Multiplier',
              dupont_5step.equity_multiplier,
              'Average Total Assets / Average Equity',
              '5-Step DuPont'
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
