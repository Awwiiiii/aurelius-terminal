import React from 'react';
import type {
  MetricDiagnosticSchema,
  MetricProvenanceSchema,
  ProvenanceAuditTarget,
} from '../../types/advancedFundamentals';
import type { MetricResultSchema, MetricStatus } from '../../types/fundamental';
import { MetricStatusBadge } from './MetricStatusBadge';

interface Props {
  metric?: MetricResultSchema | null;
  metricLabel?: string;
  auditTarget?: ProvenanceAuditTarget | null;
  onClose: () => void;
}

export const ProvenanceModal: React.FC<Props> = ({
  metric,
  metricLabel,
  auditTarget,
  onClose,
}) => {
  // Normalize between M7A MetricResultSchema and M7B.2 ProvenanceAuditTarget
  const targetName: string =
    auditTarget?.metricName || metricLabel || metric?.metric_id || 'Financial Metric';
  const category: string =
    auditTarget?.category || metric?.category || 'ANALYTICS';
  const periodLabel: string =
    auditTarget?.periodLabel || metric?.period_key || 'Period';
  const formattedValue: string =
    auditTarget?.formattedValue || metric?.formatted_value || '—';
  const status: string = auditTarget?.status || metric?.status || 'VALID';
  const isDerived: boolean =
    auditTarget?.isDerived !== undefined ? auditTarget.isDerived : (metric?.is_derived ?? true);
  const provenance: MetricProvenanceSchema =
    auditTarget?.provenance || metric?.provenance || {
      formula_id: 'UNKNOWN',
      methodology_version: '1.0.0',
      source_fact_ids: [],
      source_concepts: [],
      source_periods: [],
      provider: 'aurelius_engine',
    };
  const diagnostics: MetricDiagnosticSchema[] =
    auditTarget?.diagnostics || metric?.diagnostics || [];
  const fallbackUsed: boolean = auditTarget?.allowFallbackUsed ?? false;

  return (
    <div className="provenance-modal-overlay" onClick={onClose}>
      <div
        className="provenance-modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="provenance-modal-header">
          <div>
            <span className="provenance-modal-category">
              {category} • {periodLabel}
            </span>
            <h2 className="provenance-modal-title">{targetName}</h2>
          </div>
          <button
            type="button"
            className="provenance-modal-close"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <div className="provenance-modal-body">
          <div className="provenance-stat-card">
            <div className="stat-label">CALCULATED / DERIVED VALUE</div>
            <div className="stat-value-row">
              <span className="stat-value">{formattedValue}</span>
              <MetricStatusBadge
                status={status as MetricStatus}
                diagnosticCount={diagnostics.length}
              />
              <span className="badge-derived">
                {isDerived ? 'DERIVED' : 'REPORTED'}
              </span>
              {fallbackUsed && (
                <span className="badge-fallback-active" title="Point-in-time ending denominator fallback was applied">
                  PIT FALLBACK ACTIVE
                </span>
              )}
            </div>
          </div>

          <div className="provenance-section">
            <h3 className="section-title">AUDITABLE METHODOLOGY &amp; FORMULA</h3>
            <div className="provenance-field">
              <span className="field-name">Formula ID:</span>
              <code className="field-code">{provenance.formula_id}</code>
            </div>
            <div className="provenance-field">
              <span className="field-name">Methodology Version:</span>
              <span className="field-val">{provenance.methodology_version}</span>
            </div>
            <div className="provenance-field">
              <span className="field-name">Data Provider:</span>
              <span className="field-val">{provenance.provider}</span>
            </div>
            {provenance.methodology_notes && (
              <div className="provenance-notes">
                <strong>Methodology Notes:</strong> {provenance.methodology_notes}
              </div>
            )}
          </div>

          <div className="provenance-section">
            <h3 className="section-title">IMMUTABLE SOURCE FACTS &amp; CONCEPTS</h3>
            <div className="provenance-field">
              <span className="field-name">Source Concepts:</span>
              <div className="tag-list">
                {provenance.source_concepts && provenance.source_concepts.length > 0 ? (
                  provenance.source_concepts.map((concept, idx) => (
                    <span key={`${concept}-${idx}`} className="concept-tag">
                      {concept}
                    </span>
                  ))
                ) : (
                  <span className="field-val-muted">None (direct calculation)</span>
                )}
              </div>
            </div>
            <div className="provenance-field">
              <span className="field-name">Source Periods:</span>
              <div className="tag-list">
                {provenance.source_periods && provenance.source_periods.length > 0 ? (
                  provenance.source_periods.map((p, idx) => (
                    <span key={`${p}-${idx}`} className="period-tag">
                      {p}
                    </span>
                  ))
                ) : (
                  <span className="field-val-muted">None specified</span>
                )}
              </div>
            </div>
            <div className="provenance-field">
              <span className="field-name">Source Fact IDs:</span>
              <div className="fact-id-list">
                {provenance.source_fact_ids && provenance.source_fact_ids.length > 0 ? (
                  provenance.source_fact_ids.map((id, idx) => (
                    <code key={`${id}-${idx}`} className="fact-id-item">
                      {id}
                    </code>
                  ))
                ) : (
                  <span className="field-val-muted">None (fact unavailable or not required)</span>
                )}
              </div>
            </div>
          </div>

          {diagnostics.length > 0 && (
            <div className="provenance-section diagnostics-section">
              <h3 className="section-title">AUDIT DIAGNOSTICS &amp; WARNINGS</h3>
              {diagnostics.map((diag, idx) => (
                <div key={idx} className="diagnostic-item">
                  <div className="diagnostic-code-badge">{diag.code}</div>
                  <div className="diagnostic-message">{diag.message}</div>
                  {diag.details && Object.keys(diag.details).length > 0 && (
                    <pre className="diagnostic-details">
                      {JSON.stringify(diag.details, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="provenance-modal-footer">
          <button
            type="button"
            className="provenance-btn-primary"
            onClick={onClose}
          >
            CLOSE AUDIT INSPECTOR
          </button>
        </div>
      </div>
    </div>
  );
};
