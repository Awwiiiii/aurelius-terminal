import React from 'react';
import type {
  AdvancedFundamentalsResponse,
  MetricValueResponse,
  ProvenanceAuditTarget,
} from '../../types/advancedFundamentals';
import type { MetricStatus } from '../../types/fundamental';
import { formatCompactFinancialValue } from '../../utils/formatters';
import { MetricStatusBadge } from './MetricStatusBadge';

interface Props {
  data: AdvancedFundamentalsResponse;
  allowFallback: boolean;
  onInspectProvenance: (target: ProvenanceAuditTarget) => void;
}

export const RoicNopatPanel: React.FC<Props> = ({
  data,
  allowFallback,
  onInspectProvenance,
}) => {
  const {
    effective_tax_rate,
    nopat,
    invested_capital,
    average_invested_capital,
    roic,
    period,
  } = data;

  const renderMetricCard = (
    title: string,
    metric: MetricValueResponse,
    subtitle: string,
    isHero: boolean = false
  ) => {
    const isUnavailable = metric.status === 'UNAVAILABLE';
    const isDistorted = metric.status === 'DISTORTED';
    const primaryDiagnostic = metric.diagnostics && metric.diagnostics.length > 0
      ? metric.diagnostics[0]
      : null;

    const displayValue = isUnavailable
      ? '—'
      : formatCompactFinancialValue(
          metric.value !== null && metric.value !== undefined ? metric.value : metric.formatted_value,
          metric.unit
        );

    return (
      <div
        className={`roic-metric-card ${isHero ? 'roic-hero-card' : ''} ${
          isUnavailable ? 'metric-state-unavailable' : ''
        } ${isDistorted ? 'metric-state-distorted' : ''}`}
      >
        <div className="metric-card-header">
          <div>
            <div className="metric-card-title">{title}</div>
            <div className="metric-card-subtitle">{subtitle}</div>
          </div>
          <MetricStatusBadge
            status={metric.status as MetricStatus}
            diagnosticCount={metric.diagnostics.length}
          />
        </div>

        <div className="metric-card-body">
          {isUnavailable ? (
            <div className="unavailable-display">
              <div className="unavailable-label">UNAVAILABLE</div>
              {primaryDiagnostic ? (
                <div className="unavailable-reason" title={primaryDiagnostic.message}>
                  <span className="reason-tag">REASON:</span> {primaryDiagnostic.message}
                </div>
              ) : (
                <div className="unavailable-reason">
                  <span className="reason-tag">REASON:</span> Required financial statement inputs are missing or non-positive.
                </div>
              )}
            </div>
          ) : isDistorted ? (
            <div className="distorted-display">
              <div className="distorted-value">{displayValue}</div>
              {primaryDiagnostic && (
                <div className="distorted-warning">
                  ⚠ {primaryDiagnostic.message}
                </div>
              )}
            </div>
          ) : (
            <div className="metric-value-display">
              <span className="metric-primary-value">{displayValue}</span>
              {metric.unit && <span className="metric-unit-tag">{metric.unit}</span>}
            </div>
          )}
        </div>

        <div className="metric-card-footer">
          <button
            type="button"
            className="audit-inspect-btn"
            onClick={() =>
              onInspectProvenance({
                metricName: title,
                formattedValue: displayValue,
                periodLabel: period.display_label || period.period_key,
                status: metric.status,
                unit: metric.unit,
                currency: metric.currency,
                isDerived: metric.is_derived,
                provenance: metric.provenance,
                diagnostics: metric.diagnostics,
                category: 'ROIC & NOPAT',
                allowFallbackUsed: allowFallback && metric.provenance.formula_id.includes('POINT_IN_TIME'),
              })
            }
          >
            ◈ VIEW PROVENANCE
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="roic-nopat-panel">
      <div className="panel-section-header">
        <div>
          <div className="panel-badge">CORE OPERATIONAL PRODUCTIVITY</div>
          <h3 className="panel-title">Return on Invested Capital (ROIC) &amp; NOPAT</h3>
        </div>
        <div className="period-indicator">
          {period.display_label || period.period_key} • {data.period_type}
        </div>
      </div>

      <div className="roic-cards-grid">
        {/* Hero Card: ROIC */}
        {renderMetricCard(
          'ROIC (Return on Invested Capital)',
          roic,
          'NOPAT / Average Invested Capital (Strict 2-Point Average)',
          true
        )}

        {/* Supporting Card: NOPAT */}
        {renderMetricCard(
          'NOPAT (Net Operating Profit After Tax)',
          nopat,
          'EBIT × (1 - Effective Tax Rate)'
        )}

        {/* Supporting Card: Effective Tax Rate */}
        {renderMetricCard(
          'Effective Tax Rate (ETR)',
          effective_tax_rate,
          'Income Tax Expense / Pretax Income (EBT)'
        )}

        {/* Supporting Card: Average Invested Capital */}
        {renderMetricCard(
          'Average Invested Capital',
          average_invested_capital,
          '(Beginning IC + Ending IC) / 2'
        )}

        {/* Supporting Card: Point-in-Time Invested Capital */}
        {renderMetricCard(
          'Ending Invested Capital',
          invested_capital,
          'Gross Debt + Stockholders Equity - Cash & Equivalents'
        )}
      </div>
    </div>
  );
};
