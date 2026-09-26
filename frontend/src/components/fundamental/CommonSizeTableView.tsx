import React, { useState } from 'react';
import type {
  CommonSizeItemSchema,
  CommonSizeStatementsResponse,
  CommonSizeTableSchema,
  ProvenanceAuditTarget,
} from '../../types/advancedFundamentals';
import type { MetricStatus } from '../../types/fundamental';
import { formatMarketCap } from '../../utils/formatters';
import { MetricStatusBadge } from './MetricStatusBadge';

interface Props {
  data: CommonSizeStatementsResponse;
  onInspectProvenance: (target: ProvenanceAuditTarget) => void;
}

export const CommonSizeTableView: React.FC<Props> = ({
  data,
  onInspectProvenance,
}) => {
  const [activeTab, setActiveTab] = useState<'IS' | 'BS' | 'CF'>('IS');

  const { income_statement, balance_sheet, cash_flow_statement, period_type } = data;

  const currentStatement: CommonSizeTableSchema =
    activeTab === 'IS'
      ? income_statement
      : activeTab === 'BS'
      ? balance_sheet
      : cash_flow_statement;

  const formatConceptLabel = (name: string): string => {
    return name
      .replace(/_/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  const formatCurrency = (val: string | number | null | undefined): string => {
    if (val === null || val === undefined || val === '') return '—';
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num)) return '—';
    return formatMarketCap(num);
  };

  const formatPercent = (val: string | number | null | undefined): string => {
    if (val === null || val === undefined || val === '') return '—';
    const num = typeof val === 'string' ? parseFloat(val) : val;
    if (isNaN(num)) return '—';
    return `${num.toFixed(2)}%`;
  };

  return (
    <div className="common-size-view">
      <div className="panel-section-header">
        <div>
          <div className="panel-badge">NORMALIZED FINANCIAL RATIOS</div>
          <h3 className="panel-title">Common-Size Statements Presentation</h3>
        </div>
        <div className="period-indicator">
          {period_type} • Base: {currentStatement.base_concept_name}
        </div>
      </div>

      {/* Statement Tabs */}
      <div className="common-size-tabs-bar">
        <button
          type="button"
          className={`cs-tab-btn ${activeTab === 'IS' ? 'active' : ''}`}
          onClick={() => setActiveTab('IS')}
        >
          INCOME STATEMENT (% REVENUE)
        </button>
        <button
          type="button"
          className={`cs-tab-btn ${activeTab === 'BS' ? 'active' : ''}`}
          onClick={() => setActiveTab('BS')}
        >
          BALANCE SHEET (% ASSETS)
        </button>
        <button
          type="button"
          className={`cs-tab-btn ${activeTab === 'CF' ? 'active' : ''}`}
          onClick={() => setActiveTab('CF')}
        >
          CASH FLOW (% REVENUE)
        </button>
      </div>

      {/* Statement Metadata & Title Banner */}
      <div className="common-size-statement-header">
        <div className="statement-title-info">
          {/* CRITICAL: display_title directly from backend ensures no "TTM Balance Sheet" */}
          <h4 className="statement-display-title">{currentStatement.display_title}</h4>
          <span className="statement-base-info">
            Scaling Base: <strong>{currentStatement.base_concept_name}</strong> (
            {formatCurrency(currentStatement.base_value)})
          </span>
        </div>
        <div className="statement-status-info">
          <MetricStatusBadge
            status={currentStatement.status as MetricStatus}
            diagnosticCount={currentStatement.diagnostics.length}
          />
        </div>
      </div>

      {/* Table */}
      <div className="common-size-table-container">
        <table className="common-size-table">
          <thead>
            <tr>
              <th className="th-cs-concept">LINE ITEM</th>
              <th className="th-cs-reported">REPORTED VALUE</th>
              <th className="th-cs-percent">COMMON-SIZE %</th>
              <th className="th-cs-status">STATUS</th>
              <th className="th-cs-audit">AUDIT</th>
            </tr>
          </thead>
          <tbody>
            {currentStatement.items.map((item: CommonSizeItemSchema, idx: number) => {
              const isBaseItem =
                item.concept_name === currentStatement.base_concept_name;
              const isUnavailable = item.status === 'UNAVAILABLE';
              const diag = item.diagnostics && item.diagnostics.length > 0 ? item.diagnostics[0] : null;

              return (
                <tr
                  key={`${item.concept_name}-${idx}`}
                  className={`cs-table-row ${isBaseItem ? 'cs-row-base' : ''} ${
                    isUnavailable ? 'cs-row-unavailable' : ''
                  }`}
                >
                  <td className="td-cs-concept">
                    <span className="concept-display-name">
                      {formatConceptLabel(item.concept_name)}
                    </span>
                    <span className="concept-key-tag">{item.concept_name}</span>
                  </td>

                  <td className="td-cs-reported">
                    {formatCurrency(item.reported_value)}
                  </td>

                  <td className="td-cs-percent">
                    {isUnavailable ? (
                      <span className="val-unavailable" title={diag?.message || 'Value unavailable'}>
                        —
                      </span>
                    ) : (
                      <span className="val-percent">{formatPercent(item.common_size_percent)}</span>
                    )}
                  </td>

                  <td className="td-cs-status">
                    <MetricStatusBadge
                      status={item.status as MetricStatus}
                      diagnosticCount={item.diagnostics.length}
                    />
                  </td>

                  <td className="td-cs-audit">
                    <button
                      type="button"
                      className="audit-inspect-btn-mini"
                      onClick={() =>
                        onInspectProvenance({
                          metricName: `${formatConceptLabel(item.concept_name)} (% Common-Size)`,
                          formattedValue: formatPercent(item.common_size_percent),
                          periodLabel: currentStatement.period.display_label || currentStatement.period.period_key,
                          status: item.status,
                          unit: 'PERCENT',
                          isDerived: true,
                          provenance: item.provenance,
                          diagnostics: item.diagnostics,
                          category: `COMMON-SIZE ${currentStatement.statement_type}`,
                        })
                      }
                    >
                      PROVENANCE
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
