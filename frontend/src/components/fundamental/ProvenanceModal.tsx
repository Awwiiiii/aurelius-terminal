import React from 'react';
import type { MetricResultSchema } from '../../types/fundamental';
import { MetricStatusBadge } from './MetricStatusBadge';

interface Props {
  metric: MetricResultSchema;
  metricLabel: string;
  onClose: () => void;
}

export const ProvenanceModal: React.FC<Props> = ({
  metric,
  metricLabel,
  onClose,
}) => {
  const { provenance, diagnostics } = metric;

  return (
    <div className="provenance-modal-overlay" onClick={onClose}>
      <div
        className="provenance-modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="provenance-modal-header">
          <div>
            <span className="provenance-modal-category">
              {metric.category} • {metric.period_key}
            </span>
            <h2 className="provenance-modal-title">{metricLabel}</h2>
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
            <div className="stat-label">CALCULATED VALUE</div>
            <div className="stat-value-row">
              <span className="stat-value">{metric.formatted_value}</span>
              <MetricStatusBadge
                status={metric.status}
                diagnosticCount={diagnostics.length}
              />
              <span className="badge-derived">
                {metric.is_derived ? 'DERIVED' : 'REPORTED'}
              </span>
            </div>
          </div>

          <div className="provenance-section">
            <h3 className="section-title">AUDITABLE METHODOLOGY & FORMULA</h3>
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
            <h3 className="section-title">IMMUTABLE SOURCE FACTS & CONCEPTS</h3>
            <div className="provenance-field">
              <span className="field-name">Source Concepts:</span>
              <div className="tag-list">
                {provenance.source_concepts.map((concept) => (
                  <span key={concept} className="concept-tag">
                    {concept}
                  </span>
                ))}
              </div>
            </div>
            <div className="provenance-field">
              <span className="field-name">Source Periods:</span>
              <div className="tag-list">
                {provenance.source_periods.map((p) => (
                  <span key={p} className="period-tag">
                    {p}
                  </span>
                ))}
              </div>
            </div>
            <div className="provenance-field">
              <span className="field-name">Source Fact IDs:</span>
              <div className="fact-id-list">
                {provenance.source_fact_ids.length > 0 ? (
                  provenance.source_fact_ids.map((id) => (
                    <code key={id} className="fact-id-item">
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
              <h3 className="section-title">AUDIT DIAGNOSTICS & WARNINGS</h3>
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
