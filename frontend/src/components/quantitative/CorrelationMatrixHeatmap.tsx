import React, { useState } from 'react';
import type { MultiAssetCorrelationMatrixResponse } from '../../types/quantitative';

interface CorrelationMatrixHeatmapProps {
  data: MultiAssetCorrelationMatrixResponse | null;
  isLoading: boolean;
  onUpdateTickers: (tickers: string[]) => void;
}

const PRESETS: { label: string; tickers: string[] }[] = [
  { label: 'Mega-Cap Tech', tickers: ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN'] },
  { label: 'Semiconductors', tickers: ['NVDA', 'AMD', 'INTC', 'TSM', 'QCOM'] },
  { label: 'ETFs / Macro', tickers: ['SPY', 'QQQ', 'IWM', 'TLT', 'GLD'] },
];

export const CorrelationMatrixHeatmap: React.FC<
  CorrelationMatrixHeatmapProps
> = ({ data, isLoading, onUpdateTickers }) => {
  const [metricMode, setMetricMode] = useState<'CORRELATION' | 'COVARIANCE'>(
    'CORRELATION'
  );
  const [tickerInput, setTickerInput] = useState<string>(
    data ? data.tickers.join(', ') : 'AAPL, MSFT, NVDA, GOOGL'
  );
  const [hoveredCell, setHoveredCell] = useState<{
    row: number;
    col: number;
  } | null>(null);

  const handleApply = (e: React.FormEvent) => {
    e.preventDefault();
    const list = tickerInput
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    if (list.length >= 2) {
      onUpdateTickers(list);
    }
  };

  const handleSelectPreset = (preset: { tickers: string[] }) => {
    setTickerInput(preset.tickers.join(', '));
    onUpdateTickers(preset.tickers);
  };

  // Color generator for Pearson correlation in [-1, +1]
  const getCorrelationColor = (valStr: string | null) => {
    if (valStr === null) return 'rgba(40, 40, 45, 0.5)';
    const val = parseFloat(valStr);
    if (isNaN(val)) return 'rgba(40, 40, 45, 0.5)';

    if (val >= 0) {
      // 0 -> #1e1e24, 1.0 -> #10b981 (emerald)
      const intensity = Math.min(1, Math.max(0, val));
      const r = Math.round(30 + intensity * (16 - 30));
      const g = Math.round(30 + intensity * (185 - 30));
      const b = Math.round(36 + intensity * (129 - 36));
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      // 0 -> #1e1e24, -1.0 -> #ef4444 (red)
      const intensity = Math.min(1, Math.max(0, -val));
      const r = Math.round(30 + intensity * (239 - 30));
      const g = Math.round(30 + intensity * (68 - 30));
      const b = Math.round(36 + intensity * (68 - 36));
      return `rgb(${r}, ${g}, ${b})`;
    }
  };

  const tickers = data?.tickers ?? [];
  const matrix =
    metricMode === 'CORRELATION'
      ? data?.correlation_matrix ?? []
      : data?.covariance_matrix ?? [];

  return (
    <div className="quant-heatmap-panel">
      {/* Universe Toolbar */}
      <div className="quant-heatmap-toolbar">
        <form onSubmit={handleApply} className="quant-ticker-form">
          <label className="quant-toolbar-label" htmlFor="quant-ticker-input">
            PORTFOLIO / UNIVERSE (MIN 2 TICKERS):
          </label>
          <div className="quant-input-group">
            <input
              id="quant-ticker-input"
              type="text"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value)}
              placeholder="e.g. AAPL, MSFT, NVDA"
              className="quant-text-input"
            />
            <button
              type="submit"
              className="quant-submit-btn"
              disabled={isLoading}
            >
              {isLoading ? 'COMPUTING...' : 'COMPUTE MATRIX'}
            </button>
          </div>
        </form>

        <div className="quant-presets-group">
          <span className="quant-toolbar-label">PRESETS:</span>
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              className="quant-preset-btn"
              onClick={() => handleSelectPreset(p)}
              disabled={isLoading}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Metric Mode Toggle and Alignment Status */}
      <div className="quant-matrix-controls">
        <div className="quant-mode-toggle">
          <button
            type="button"
            className={`quant-toggle-btn ${
              metricMode === 'CORRELATION' ? 'active' : ''
            }`}
            onClick={() => setMetricMode('CORRELATION')}
          >
            PEARSON CORRELATION (r)
          </button>
          <button
            type="button"
            className={`quant-toggle-btn ${
              metricMode === 'COVARIANCE' ? 'active' : ''
            }`}
            onClick={() => setMetricMode('COVARIANCE')}
          >
            SAMPLE COVARIANCE (Cov)
          </button>
        </div>

        {data && (
          <div className="quant-alignment-info">
            <span>
              INNER DATE ALIGNMENT:{' '}
              <strong>{data.common_dates_count} common trading sessions</strong>
            </span>
            <span className="separator">•</span>
            <span>
              {data.start_date} to {data.end_date}
            </span>
          </div>
        )}
      </div>

      {/* Grid Container */}
      <div className="quant-matrix-grid-wrapper">
        {isLoading ? (
          <div className="quant-loading-indicator">
            COMPUTING INNER ALIGNMENT AND MULTI-ASSET MATRIX...
          </div>
        ) : !data || tickers.length === 0 ? (
          <div className="quant-empty-state">
            Enter at least 2 tickers above to construct correlation matrix.
          </div>
        ) : (
          <div className="quant-matrix-table-container">
            <table className="quant-matrix-table">
              <thead>
                <tr>
                  <th className="quant-matrix-corner">ASSET</th>
                  {tickers.map((t) => (
                    <th key={`col-${t}`} className="quant-matrix-col-header">
                      {t}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tickers.map((rowTicker, rIdx) => (
                  <tr key={`row-${rowTicker}`}>
                    <td className="quant-matrix-row-header">{rowTicker}</td>
                    {tickers.map((_colTicker, cIdx) => {
                      const val = matrix[rIdx]?.[cIdx] ?? null;
                      const isHovered =
                        hoveredCell?.row === rIdx && hoveredCell?.col === cIdx;
                      const isDiagonal = rIdx === cIdx;

                      const bgColor =
                        metricMode === 'CORRELATION'
                          ? getCorrelationColor(val)
                          : isDiagonal
                            ? 'rgba(56, 189, 248, 0.25)'
                            : 'rgba(30, 30, 36, 0.9)';

                      return (
                        <td
                          key={`cell-${rIdx}-${cIdx}`}
                          className={`quant-matrix-cell ${
                            isHovered ? 'hovered' : ''
                          } ${isDiagonal ? 'diagonal' : ''}`}
                          style={{ backgroundColor: bgColor }}
                          onMouseEnter={() =>
                            setHoveredCell({ row: rIdx, col: cIdx })
                          }
                          onMouseLeave={() => setHoveredCell(null)}
                        >
                          <span className="cell-value">
                            {val !== null
                              ? metricMode === 'CORRELATION'
                                ? parseFloat(val).toFixed(4)
                                : parseFloat(val).toFixed(6)
                              : '—'}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Hovered Cell Readout */}
            {hoveredCell !== null && data && (
              <div className="quant-cell-inspector">
                <span className="inspector-pair">
                  {tickers[hoveredCell.row]} ↔ {tickers[hoveredCell.col]}
                </span>
                <span className="inspector-metric">
                  {metricMode === 'CORRELATION'
                    ? `Pearson Correlation: ${
                        data.correlation_matrix[hoveredCell.row]?.[
                          hoveredCell.col
                        ] ?? 'N/A'
                      }`
                    : `Sample Covariance: ${
                        data.covariance_matrix[hoveredCell.row]?.[
                          hoveredCell.col
                        ] ?? 'N/A'
                      }`}
                </span>
                <span className="inspector-sessions">
                  Common Trading Sessions: {data.common_dates_count}
                </span>
              </div>
            )}

            {/* Matrix Legend */}
            {metricMode === 'CORRELATION' && (
              <div className="quant-heatmap-legend">
                <span className="legend-label">Negative (-1.0)</span>
                <div className="quant-gradient-bar" />
                <span className="legend-label">Positive (+1.0)</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
