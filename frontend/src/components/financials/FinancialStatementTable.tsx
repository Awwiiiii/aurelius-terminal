import React, { useMemo, useState } from 'react';
import type {
  FinancialMatrixRowSchema,
  FinancialPeriodSchema,
  FinancialStatementMatrixResponse,
} from '../../types/financials';

interface FinancialStatementTableProps {
  matrix: FinancialStatementMatrixResponse;
}

type DisplayScale = 'UNITS' | 'THOUSANDS' | 'MILLIONS' | 'BILLIONS';

export const FinancialStatementTable: React.FC<FinancialStatementTableProps> = ({
  matrix,
}) => {
  const [scale, setScale] = useState<DisplayScale>('MILLIONS');
  const [showOnlyCanonical, setShowOnlyCanonical] = useState<boolean>(false);

  const scaleDivisor = useMemo(() => {
    switch (scale) {
      case 'BILLIONS':
        return 1_000_000_000;
      case 'MILLIONS':
        return 1_000_000;
      case 'THOUSANDS':
        return 1_000;
      case 'UNITS':
      default:
        return 1;
    }
  }, [scale]);

  const scaleLabel = useMemo(() => {
    switch (scale) {
      case 'BILLIONS':
        return 'in Billions';
      case 'MILLIONS':
        return 'in Millions';
      case 'THOUSANDS':
        return 'in Thousands';
      case 'UNITS':
      default:
        return 'in Whole Units';
    }
  }, [scale]);

  const filteredRows = useMemo(() => {
    if (!showOnlyCanonical) {
      return matrix.rows;
    }
    return matrix.rows.filter((r) => r.is_canonical);
  }, [matrix.rows, showOnlyCanonical]);

  const formatCell = (val: string | number | null | undefined): React.ReactNode => {
    if (val === null || val === undefined || val === '') {
      return <span className="cell-missing">—</span>;
    }

    const num = typeof val === 'number' ? val : parseFloat(String(val));
    if (isNaN(num)) {
      return <span className="cell-missing">—</span>;
    }

    const scaled = num / scaleDivisor;
    const isNegative = scaled < 0;
    const absVal = Math.abs(scaled);

    const formattedAbs = absVal.toLocaleString(undefined, {
      minimumFractionDigits: scale === 'BILLIONS' ? 2 : scale === 'MILLIONS' ? 1 : 0,
      maximumFractionDigits: scale === 'BILLIONS' ? 2 : scale === 'MILLIONS' ? 1 : 0,
    });

    if (isNegative) {
      return <span className="cell-negative">({formattedAbs})</span>;
    }
    return <span className="cell-positive">{formattedAbs}</span>;
  };

  if (!matrix.periods || matrix.periods.length === 0 || filteredRows.length === 0) {
    return (
      <div className="financials-empty-state">
        <span className="empty-icon">▤</span>
        <div className="empty-title">NO FINANCIAL STATEMENTS DISCLOSED</div>
        <div className="empty-desc">
          No historical {matrix.statement_type.replace('_', ' ').toLowerCase()} data was
          found for {matrix.company_id} ({matrix.frequency.toLowerCase()}).
        </div>
      </div>
    );
  }

  return (
    <div className="financials-table-container">
      <div className="financials-toolbar">
        <div className="toolbar-info">
          <span className="metric-badge currency-badge">
            CURRENCY: {matrix.currency || 'USD'}
          </span>
          <span className="metric-badge scale-badge">SCALE: {scaleLabel}</span>
          <span className="metric-badge count-badge">
            {filteredRows.length} LINE ITEMS • {matrix.periods.length} PERIODS
          </span>
        </div>

        <div className="toolbar-controls">
          <div className="scale-selector">
            <span className="control-label">SCALE:</span>
            <button
              type="button"
              className={`scale-btn ${scale === 'MILLIONS' ? 'active' : ''}`}
              onClick={() => setScale('MILLIONS')}
            >
              $M
            </button>
            <button
              type="button"
              className={`scale-btn ${scale === 'BILLIONS' ? 'active' : ''}`}
              onClick={() => setScale('BILLIONS')}
            >
              $B
            </button>
            <button
              type="button"
              className={`scale-btn ${scale === 'THOUSANDS' ? 'active' : ''}`}
              onClick={() => setScale('THOUSANDS')}
            >
              $K
            </button>
            <button
              type="button"
              className={`scale-btn ${scale === 'UNITS' ? 'active' : ''}`}
              onClick={() => setScale('UNITS')}
            >
              RAW
            </button>
          </div>

          <div className="filter-toggle">
            <button
              type="button"
              className={`toggle-btn ${showOnlyCanonical ? 'active' : ''}`}
              onClick={() => setShowOnlyCanonical(!showOnlyCanonical)}
            >
              {showOnlyCanonical ? 'CANONICAL METRICS' : 'ALL REPORTED ITEMS'}
            </button>
          </div>
        </div>
      </div>

      <div className="financials-grid-scroll">
        <table className="financials-matrix-table">
          <thead>
            <tr>
              <th className="sticky-col header-line-item">LINE ITEM</th>
              {matrix.periods.map((p: FinancialPeriodSchema) => (
                <th key={p.period_key} className="header-period">
                  <div className="period-title">{p.display_label}</div>
                  <div className="period-subtitle">
                    {p.period_type === 'INSTANT' ? 'AS OF' : 'ENDED'} {p.period_key}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row: FinancialMatrixRowSchema) => (
              <tr
                key={row.concept_key}
                className={`matrix-row ${
                  row.is_canonical ? 'canonical-row' : 'detailed-row'
                }`}
              >
                <td className="sticky-col cell-line-item">
                  <span className="row-indicator">{row.is_canonical ? '◈' : '·'}</span>
                  <span className="row-name" title={row.concept_key}>
                    {row.display_name}
                  </span>
                  {row.is_canonical && (
                    <span className="canonical-tag">CANONICAL</span>
                  )}
                </td>
                {matrix.periods.map((p: FinancialPeriodSchema) => (
                  <td key={p.period_key} className="cell-value">
                    {formatCell(row.values_by_period[p.period_key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
