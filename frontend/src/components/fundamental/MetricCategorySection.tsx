import React from 'react';
import type { FinancialPeriodSchema } from '../../types/financials';
import type {
  MetricCategory,
  MetricResultSchema,
} from '../../types/fundamental';
import { MetricStatusBadge } from './MetricStatusBadge';

export interface MetricDefinition {
  id: string;
  label: string;
  formulaDescription?: string;
  unit?: string;
}

interface Props {
  category: MetricCategory;
  title: string;
  description: string;
  metricDefs: MetricDefinition[];
  periods: FinancialPeriodSchema[];
  metrics: Record<string, MetricResultSchema[]>;
  onInspectMetric: (metric: MetricResultSchema, label: string) => void;
}

export const MetricCategorySection: React.FC<Props> = ({
  category,
  title,
  description,
  metricDefs,
  periods,
  metrics,
  onInspectMetric,
}) => {
  return (
    <div className="metric-category-section" id={`category-${category.toLowerCase()}`}>
      <div className="category-section-header">
        <div className="category-header-title-group">
          <span className="category-badge">{category}</span>
          <h3 className="category-title">{title}</h3>
        </div>
        <p className="category-description">{description}</p>
      </div>

      <div className="category-table-wrapper">
        <table className="fundamental-matrix-table">
          <thead>
            <tr>
              <th className="th-metric-name">METRIC</th>
              {periods.map((p) => (
                <th key={p.period_key} className="th-period">
                  <div className="th-period-label">{p.display_label || p.period_key}</div>
                  <div className="th-period-sub">
                    {p.end_date ?? p.instant_date ?? ''}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metricDefs.map((def) => {
              const metricList = metrics[def.id] || [];

              return (
                <tr key={def.id} className="fundamental-metric-row">
                  <td className="td-metric-name">
                    <div className="metric-name-primary">{def.label}</div>
                    {def.formulaDescription && (
                      <div className="metric-description-sub">
                        {def.formulaDescription}
                      </div>
                    )}
                  </td>
                  {periods.map((period) => {
                    const result = metricList.find(
                      (m) => m.period_key === period.period_key
                    );

                    if (!result) {
                      return (
                        <td key={period.period_key} className="td-metric-val empty-cell">
                          <span className="val-missing">—</span>
                        </td>
                      );
                    }

                    const isDistorted = result.status === 'DISTORTED';
                    const isUnavailable = result.status === 'UNAVAILABLE';
                    const isNA = result.status === 'NOT_APPLICABLE';
                    const isValid = result.status === 'VALID';
                    const hasDiagnostics = result.diagnostics && result.diagnostics.length > 0;

                    let displayVal = result.formatted_value;
                    if (!displayVal || isUnavailable) {
                      displayVal = '—';
                    } else if (isNA) {
                      displayVal = 'N/A';
                    }

                    return (
                      <td
                        key={period.period_key}
                        className={`td-metric-val status-${result.status.toLowerCase()}`}
                        onClick={() => onInspectMetric(result, def.label)}
                        title="Click to inspect auditable methodology, formula, and source facts"
                      >
                        <div className="metric-val-cell-content">
                          <div className="metric-val-row">
                            <span
                              className={`metric-val-text ${
                                isDistorted ? 'text-distorted' : ''
                              }`}
                            >
                              {displayVal}
                            </span>
                            <button
                              type="button"
                              className="inspect-btn"
                              aria-label={`Inspect ${def.label} provenance`}
                              onClick={(e) => {
                                e.stopPropagation();
                                onInspectMetric(result, def.label);
                              }}
                            >
                              AUDIT
                            </button>
                          </div>

                          <div className="metric-status-subrow">
                            {!isValid && (
                              <MetricStatusBadge
                                status={result.status}
                                diagnosticCount={result.diagnostics.length}
                              />
                            )}
                            {isValid && hasDiagnostics && (
                              <span
                                className="diag-warning-chip"
                                title={result.diagnostics.map((d) => `${d.code}: ${d.message}`).join('; ')}
                              >
                                ⚠ {result.diagnostics.length}
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
