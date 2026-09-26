import React from 'react';
import type {
  AdvancedFundamentalsResponse,
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

export const QualityDiagnosticsView: React.FC<Props> = ({
  data,
  allowFallback,
  onInspectProvenance,
}) => {
  const { quality_diagnostics, period } = data;
  const { sloan_accruals, operating_quality_ratio, diagnostics_summary } = quality_diagnostics;

  const renderDiagnosticCard = (
    title: string,
    metric: MetricValueResponse,
    formulaDesc: string,
    interpretationNote: string
  ) => {
    const isUnavailable = metric.status === 'UNAVAILABLE';
    const isDistorted = metric.status === 'DISTORTED';
    const diagnostics = metric.diagnostics || [];

    // Extract persistence details if present in details
    let persistenceInfo: string | null = null;
    for (const d of diagnostics) {
      if (d.details) {
        if (d.details.consecutive_periods) {
          persistenceInfo = `${d.details.consecutive_periods} consecutive eligible periods evaluated`;
        } else if (d.details.persistence_window) {
          persistenceInfo = `Persistence window: ${d.details.persistence_window}`;
        }
      }
    }

    return (
      <div className={`quality-diag-card ${isUnavailable ? 'card-unavailable' : ''} ${isDistorted ? 'card-distorted' : ''}`}>
        <div className="diag-card-header">
          <div>
            <div className="diag-card-title">{title}</div>
            <div className="diag-card-formula">{formulaDesc}</div>
          </div>
          <MetricStatusBadge
            status={metric.status as MetricStatus}
            diagnosticCount={diagnostics.length}
          />
        </div>

        <div className="diag-card-body">
          <div className="diag-stat-row">
            <span className="diag-stat-label">CALCULATED METRIC</span>
            <span className="diag-stat-value">{metric.formatted_value}</span>
            {metric.unit && <span className="diag-stat-unit">{metric.unit}</span>}
          </div>

          {persistenceInfo && (
            <div className="diag-persistence-badge">
              <span className="persistence-icon">⏱</span>
              <span>{persistenceInfo}</span>
            </div>
          )}

          <div className="diag-interpretation-box">
            <div className="interp-label">ANALYTICAL INTERPRETATION</div>
            <p className="interp-text">{interpretationNote}</p>
          </div>

          {/* Diagnostic Messages & Warnings with strictly neutral analytical wording */}
          {diagnostics.length > 0 && (
            <div className="diag-flags-list">
              <div className="flags-header">DIAGNOSTIC FINDINGS ({diagnostics.length})</div>
              {diagnostics.map((d, idx) => {
                const isWarning = d.code.includes('WARNING') || d.code.includes('EXTREME') || d.code.includes('HIGH');
                return (
                  <div
                    key={idx}
                    className={`diag-flag-item ${isWarning ? 'flag-warning' : 'flag-info'}`}
                  >
                    <span className="flag-code">{d.code}</span>
                    <span className="flag-message">{d.message}</span>
                  </div>
                );
              })}
            </div>
          )}

          {diagnostics.length === 0 && !isUnavailable && (
            <div className="diag-benign-indicator">
              <span className="benign-icon">✓</span>
              <span>No abnormal accrual or earnings divergence flags detected for this period.</span>
            </div>
          )}
        </div>

        <div className="diag-card-footer">
          <button
            type="button"
            className="audit-inspect-btn"
            onClick={() =>
              onInspectProvenance({
                metricName: title,
                formattedValue: metric.formatted_value,
                periodLabel: period.display_label || period.period_key,
                status: metric.status,
                unit: metric.unit,
                currency: metric.currency,
                isDerived: metric.is_derived,
                provenance: metric.provenance,
                diagnostics: metric.diagnostics,
                category: 'EARNINGS QUALITY & FORENSIC DIAGNOSTICS',
                allowFallbackUsed: allowFallback && metric.provenance.formula_id.includes('POINT_IN_TIME'),
              })
            }
          >
            ◈ VIEW PROVENANCE &amp; FACT IDS
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="quality-diagnostics-view">
      <div className="panel-section-header">
        <div>
          <div className="panel-badge">FORENSIC &amp; CASH FLOW DIAGNOSTICS</div>
          <h3 className="panel-title">Earnings Quality &amp; Accrual Persistence Analysis</h3>
        </div>
        <div className="period-indicator">
          {period.display_label || period.period_key} • {data.period_type}
        </div>
      </div>

      <div className="quality-cards-grid">
        {/* 1. Sloan Accruals */}
        {renderDiagnosticCard(
          'Sloan Balance-Sheet Accruals',
          sloan_accruals,
          '[(ΔCA - ΔCash) - (ΔCL - ΔSTD) - Dep] / Average Total Assets',
          'Measures the magnitude of balance-sheet accruals relative to average total assets and can be used as a screening diagnostic for divergence between accounting accruals and cash-based activity.'
        )}

        {/* 2. Operating Quality Ratio */}
        {renderDiagnosticCard(
          'Operating Quality Ratio (OQR)',
          operating_quality_ratio,
          'Cash Flow from Operations (CFO) / Operating Income (EBIT)',
          'Evaluates the cash realization of operating profits. Ratios below 1.0 indicate operating cash flows trail operating income; persistent suppression warrants deeper working capital inspection.'
        )}
      </div>

      {/* Aggregate Diagnostics Summary */}
      {diagnostics_summary && diagnostics_summary.length > 0 && (
        <div className="diagnostics-summary-panel">
          <div className="summary-panel-header">
            <span className="summary-icon">◈</span>
            <span className="summary-title">AGGREGATE QUALITY DIAGNOSTICS SUMMARY</span>
          </div>
          <div className="summary-list">
            {diagnostics_summary.map((diag, idx) => (
              <div key={idx} className="summary-item">
                <code className="summary-code">{diag.code}</code>
                <span className="summary-text">{diag.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
