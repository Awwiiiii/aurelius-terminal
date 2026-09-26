import React, { useMemo, useState } from 'react';
import type {
  CAGRDataPointSchema,
  FundamentalTrendsResponse,
  MetricTrendSeriesSchema,
  ProvenanceAuditTarget,
  TrendDataPointSchema,
} from '../../types/advancedFundamentals';
import type { MetricStatus } from '../../types/fundamental';
import { formatCompactFinancialValue } from '../../utils/formatters';
import { MetricStatusBadge } from './MetricStatusBadge';

interface Props {
  data: FundamentalTrendsResponse;
  onInspectProvenance: (target: ProvenanceAuditTarget) => void;
}

interface MetricMeta {
  key: string;
  label: string;
  category: string;
  unit: string;
}

const CANONICAL_METRICS: MetricMeta[] = [
  { key: 'revenue', label: 'Revenue', category: 'Growth & Topline', unit: 'CURRENCY' },
  { key: 'revenue_growth', label: 'Revenue Growth', category: 'Growth & Topline', unit: 'PERCENT' },
  { key: 'gross_margin', label: 'Gross Margin', category: 'Profitability', unit: 'PERCENT' },
  { key: 'operating_margin', label: 'Operating Margin', category: 'Profitability', unit: 'PERCENT' },
  { key: 'net_margin', label: 'Net Margin', category: 'Profitability', unit: 'PERCENT' },
  { key: 'roa', label: 'Return on Assets (ROA)', category: 'Productivity', unit: 'PERCENT' },
  { key: 'roe', label: 'Return on Equity (ROE)', category: 'Productivity', unit: 'PERCENT' },
  { key: 'roic', label: 'Return on Invested Capital (ROIC)', category: 'Productivity', unit: 'PERCENT' },
  { key: 'cfo', label: 'Operating Cash Flow (CFO)', category: 'Cash Flow', unit: 'CURRENCY' },
  { key: 'fcf', label: 'Free Cash Flow (FCF)', category: 'Cash Flow', unit: 'CURRENCY' },
  { key: 'fcf_margin', label: 'FCF Margin', category: 'Cash Flow', unit: 'PERCENT' },
  { key: 'cfo_to_net_income', label: 'CFO / Net Income', category: 'Quality', unit: 'RATIO' },
  { key: 'fcf_to_net_income', label: 'FCF / Net Income', category: 'Quality', unit: 'RATIO' },
  { key: 'debt_to_ebitda', label: 'Gross Debt / EBITDA', category: 'Leverage', unit: 'RATIO' },
  { key: 'net_debt_to_ebitda', label: 'Net Debt / EBITDA', category: 'Leverage', unit: 'RATIO' },
  { key: 'cash_conversion_cycle', label: 'Cash Conversion Cycle (CCC)', category: 'Efficiency', unit: 'DAYS' },
];

export const FundamentalTrendsView: React.FC<Props> = ({
  data,
  onInspectProvenance,
}) => {
  const [selectedMetricKey, setSelectedMetricKey] = useState<string>('revenue');
  const [cagrHorizon, setCagrHorizon] = useState<'3Y' | '5Y'>('3Y');
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const seriesMap = data.series || {};
  const currentSeries: MetricTrendSeriesSchema | undefined = seriesMap[selectedMetricKey];
  const points: TrendDataPointSchema[] = currentSeries?.points || [];

  const cagrList: CAGRDataPointSchema[] = data.cagr_results?.[selectedMetricKey] || [];
  const activeCagr = cagrList.find((c) => c.horizon === cagrHorizon);

  const metricMeta = CANONICAL_METRICS.find((m) => m.key === selectedMetricKey) || {
    key: selectedMetricKey,
    label: selectedMetricKey.toUpperCase(),
    category: 'Analytics',
    unit: currentSeries?.unit || '',
  };

  // SVG Chart Geometry
  const svgWidth = 840;
  const svgHeight = 280;
  const margin = { top: 30, right: 30, bottom: 40, left: 70 };
  const innerWidth = svgWidth - margin.left - margin.right;
  const innerHeight = svgHeight - margin.top - margin.bottom;

  // Numerical series mapping
  const numericPoints = useMemo(() => {
    return points.map((p, i) => {
      const numVal = p.value !== null && p.value !== undefined ? parseFloat(String(p.value)) : null;
      return {
        point: p,
        index: i,
        numVal: numVal !== null && !isNaN(numVal) ? numVal : null,
      };
    });
  }, [points]);

  const validPoints = useMemo(() => {
    return numericPoints.filter((np) => np.numVal !== null);
  }, [numericPoints]);

  const { minVal, maxVal } = useMemo(() => {
    if (validPoints.length === 0) return { minVal: 0, maxVal: 100 };
    let min = Infinity;
    let max = -Infinity;
    for (const vp of validPoints) {
      if (vp.numVal! < min) min = vp.numVal!;
      if (vp.numVal! > max) max = vp.numVal!;
    }
    if (min === max) {
      return { minVal: min - 1, maxVal: max + 1 };
    }
    // Add 10% padding
    const pad = (max - min) * 0.1;
    return { minVal: min - pad, maxVal: max + pad };
  }, [validPoints]);

  const getX = (index: number) => {
    if (points.length <= 1) return margin.left + innerWidth / 2;
    return margin.left + (index / (points.length - 1)) * innerWidth;
  };

  const getY = (val: number) => {
    const range = maxVal - minVal;
    if (range === 0) return margin.top + innerHeight / 2;
    const norm = (val - minVal) / range;
    return margin.top + innerHeight - norm * innerHeight;
  };

  // Build SVG path
  const linePath = useMemo(() => {
    if (points.length === 0) return '';
    let d = '';
    let hasStarted = false;
    for (const np of numericPoints) {
      if (np.numVal !== null) {
        const x = getX(np.index);
        const y = getY(np.numVal);
        if (!hasStarted) {
          d += `M ${x.toFixed(1)} ${y.toFixed(1)}`;
          hasStarted = true;
        } else {
          d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
        }
      }
    }
    return d;
  }, [numericPoints, minVal, maxVal, points.length]);

  // Area path
  const areaPath = useMemo(() => {
    if (points.length === 0 || !linePath) return '';
    const valid = numericPoints.filter((np) => np.numVal !== null);
    if (valid.length === 0) return '';
    const firstX = getX(valid[0].index);
    const lastX = getX(valid[valid.length - 1].index);
    const bottomY = margin.top + innerHeight;
    return `${linePath} L ${lastX.toFixed(1)} ${bottomY} L ${firstX.toFixed(1)} ${bottomY} Z`;
  }, [linePath, numericPoints, points.length]);

  const hoveredPoint = hoverIndex !== null && points[hoverIndex] ? points[hoverIndex] : null;

  const formatPointDisplay = (p: TrendDataPointSchema | null | undefined): string => {
    if (!p || p.status === 'UNAVAILABLE' || p.formatted_value === 'UNAVAILABLE' || p.value === null) {
      return '—';
    }
    return formatCompactFinancialValue(
      p.value !== null && p.value !== undefined ? p.value : p.formatted_value,
      metricMeta.unit || currentSeries?.unit
    );
  };

  return (
    <div className="fundamental-trends-view">
      <div className="panel-section-header">
        <div>
          <div className="panel-badge">LONGITUDINAL FUNDAMENTAL TRAJECTORIES</div>
          <h3 className="panel-title">Multi-Period Trajectory &amp; Compound Growth (CAGR)</h3>
        </div>
        <div className="period-indicator">
          {data.period_type} • Frequency: {data.period_type}
        </div>
      </div>

      {/* Metric Selector Strip */}
      <div className="trends-metric-selector-bar">
        <label className="selector-label" htmlFor="metric-select">ACTIVE METRIC:</label>
        <select
          id="metric-select"
          className="metric-select-dropdown"
          value={selectedMetricKey}
          onChange={(e) => {
            setSelectedMetricKey(e.target.value);
            setHoverIndex(null);
          }}
        >
          {CANONICAL_METRICS.map((m) => (
            <option key={m.key} value={m.key}>
              [{m.category}] {m.label}
            </option>
          ))}
        </select>

        {/* Quick buttons for primary metrics */}
        <div className="quick-metrics-pills">
          {['revenue', 'operating_margin', 'roic', 'fcf', 'gross_margin'].map((k) => {
            const meta = CANONICAL_METRICS.find((m) => m.key === k);
            return (
              <button
                key={k}
                type="button"
                className={`quick-pill-btn ${selectedMetricKey === k ? 'active' : ''}`}
                onClick={() => {
                  setSelectedMetricKey(k);
                  setHoverIndex(null);
                }}
              >
                {meta?.label || k}
              </button>
            );
          })}
        </div>
      </div>

      {/* Chart & CAGR Overview Row */}
      <div className="trends-chart-row">
        {/* SVG Chart Container */}
        <div className="trends-svg-card">
          <div className="chart-header-info">
            <div>
              <span className="chart-metric-title">{metricMeta.label}</span>
              <span className="chart-period-type">({data.period_type} Trajectory)</span>
            </div>
            {points.length > 0 && (
              <div className="latest-val-badge">
                LATEST: {formatPointDisplay(points[points.length - 1])}
              </div>
            )}
          </div>

          <div className="svg-wrapper">
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              className="trends-svg"
              onMouseLeave={() => setHoverIndex(null)}
            >
              <defs>
                <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Grid Lines */}
              {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
                const y = margin.top + pct * innerHeight;
                const val = maxVal - pct * (maxVal - minVal);
                return (
                  <g key={pct}>
                    <line
                      x1={margin.left}
                      y1={y}
                      x2={svgWidth - margin.right}
                      y2={y}
                      stroke="rgba(255, 255, 255, 0.05)"
                      strokeDasharray="4 4"
                    />
                    <text
                      x={margin.left - 8}
                      y={y + 3}
                      fill="var(--text-dim)"
                      fontSize="9"
                      fontFamily="var(--font-mono)"
                      textAnchor="end"
                    >
                      {val >= 1e9
                        ? `$${(val / 1e9).toFixed(1)}B`
                        : val >= 1e6
                        ? `$${(val / 1e6).toFixed(1)}M`
                        : val.toFixed(1)}
                    </text>
                  </g>
                );
              })}

              {/* Area & Line */}
              {areaPath && <path d={areaPath} fill="url(#trendGradient)" />}
              {linePath && (
                <path
                  d={linePath}
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              )}

              {/* Data Points */}
              {numericPoints.map((np) => {
                if (np.numVal === null) return null;
                const cx = getX(np.index);
                const cy = getY(np.numVal);
                const isHovered = hoverIndex === np.index;

                return (
                  <g
                    key={np.index}
                    className="trend-point-group"
                    onMouseEnter={() => setHoverIndex(np.index)}
                  >
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isHovered ? 6 : 4}
                      fill={isHovered ? '#f59e0b' : '#38bdf8'}
                      stroke="#0b0f19"
                      strokeWidth="2"
                    />
                    {/* Period Label on X Axis */}
                    <text
                      x={cx}
                      y={svgHeight - 12}
                      fill="var(--text-dim)"
                      fontSize="9"
                      fontFamily="var(--font-mono)"
                      textAnchor="middle"
                    >
                      {np.point.period.display_label || np.point.period.period_key}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Interactive Tooltip Card */}
          {hoveredPoint && (
            <div className="trends-tooltip-bar">
              <div className="tooltip-item">
                <span className="tooltip-lbl">PERIOD:</span>
                <span className="tooltip-val">
                  {hoveredPoint.period.display_label || hoveredPoint.period.period_key} (
                  {hoveredPoint.period.end_date || hoveredPoint.period.instant_date || ''})
                </span>
              </div>
              <div className="tooltip-item">
                <span className="tooltip-lbl">VALUE:</span>
                <span className="tooltip-val val-highlight">{formatPointDisplay(hoveredPoint)}</span>
              </div>
              {hoveredPoint.yoy_change !== null && hoveredPoint.yoy_change !== undefined && (
                <div className="tooltip-item">
                  <span className="tooltip-lbl">YoY:</span>
                  <span className="tooltip-val">
                    {parseFloat(String(hoveredPoint.yoy_change)) >= 0 ? '+' : ''}
                    {parseFloat(String(hoveredPoint.yoy_change)).toFixed(2)}%
                  </span>
                </div>
              )}
              {hoveredPoint.qoq_change !== null && hoveredPoint.qoq_change !== undefined && (
                <div className="tooltip-item">
                  <span className="tooltip-lbl">QoQ:</span>
                  <span className="tooltip-val">
                    {parseFloat(String(hoveredPoint.qoq_change)) >= 0 ? '+' : ''}
                    {parseFloat(String(hoveredPoint.qoq_change)).toFixed(2)}%
                  </span>
                </div>
              )}
              {/* CRITICAL: Respect exact TTM sequential change wording, NEVER QoQ */}
              {hoveredPoint.ttm_sequential_change !== null &&
                hoveredPoint.ttm_sequential_change !== undefined && (
                  <div className="tooltip-item">
                    <span className="tooltip-lbl">TTM SEQUENTIAL CHANGE:</span>
                    <span className="tooltip-val">
                      {parseFloat(String(hoveredPoint.ttm_sequential_change)) >= 0 ? '+' : ''}
                      {parseFloat(String(hoveredPoint.ttm_sequential_change)).toFixed(2)}%
                    </span>
                  </div>
                )}
            </div>
          )}
        </div>

        {/* Compound Annual Growth Rate (CAGR) Card */}
        <div className="cagr-summary-card">
          <div className="cagr-header">
            <span className="cagr-badge">M4 CALENDAR-TIME CAGR</span>
            <div className="cagr-horizon-toggle">
              <button
                type="button"
                className={`horizon-btn ${cagrHorizon === '3Y' ? 'active' : ''}`}
                onClick={() => setCagrHorizon('3Y')}
              >
                3Y HORIZON
              </button>
              <button
                type="button"
                className={`horizon-btn ${cagrHorizon === '5Y' ? 'active' : ''}`}
                onClick={() => setCagrHorizon('5Y')}
              >
                5Y HORIZON
              </button>
            </div>
          </div>

          <div className="cagr-body">
            {activeCagr ? (
              <>
                <div className="cagr-stat">
                  <span className="cagr-lbl">{cagrHorizon} COMPOUND ANNUAL RATE</span>
                  <span className="cagr-main-val">{activeCagr.formatted_cagr}</span>
                  <MetricStatusBadge
                    status={activeCagr.status as MetricStatus}
                    diagnosticCount={activeCagr.diagnostics.length}
                  />
                </div>

                <div className="cagr-details">
                  <div className="cagr-detail-row">
                    <span className="detail-name">Anchor Window:</span>
                    <span className="detail-value">
                      {activeCagr.start_period.display_label} → {activeCagr.end_period.display_label}
                    </span>
                  </div>
                  <div className="cagr-detail-row">
                    <span className="detail-name">Exact Calendar Days:</span>
                    <span className="detail-value">{activeCagr.calendar_days} days</span>
                  </div>
                </div>

                <div className="cagr-footer-action">
                  <button
                    type="button"
                    className="audit-inspect-btn"
                    onClick={() =>
                      onInspectProvenance({
                        metricName: `${metricMeta.label} (${cagrHorizon} CAGR)`,
                        formattedValue: activeCagr.formatted_cagr,
                        periodLabel: `${activeCagr.start_period.display_label} to ${activeCagr.end_period.display_label}`,
                        status: activeCagr.status,
                        unit: 'PERCENT',
                        isDerived: true,
                        provenance: activeCagr.provenance,
                        diagnostics: activeCagr.diagnostics,
                        category: 'COMPOUND ANNUAL GROWTH RATE',
                      })
                    }
                  >
                    ◈ VIEW CAGR PROVENANCE
                  </button>
                </div>
              </>
            ) : (
              <div className="cagr-unavailable-box">
                <span className="cagr-unavail-title">CAGR NOT AVAILABLE</span>
                <span className="cagr-unavail-text">
                  Insufficient chronological filing horizon to compute {cagrHorizon} calendar-time CAGR for {metricMeta.label}.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Historical Data Points Table */}
      <div className="trends-history-table-container">
        <h4 className="history-table-title">CHRONOLOGICAL TRAJECTORY POINTS ({points.length} PERIODS)</h4>
        <table className="trends-history-table">
          <thead>
            <tr>
              <th>PERIOD</th>
              <th>CALCULATED VALUE</th>
              {data.period_type === 'ANNUAL' && <th>YoY CHANGE</th>}
              {data.period_type === 'QUARTERLY' && (
                <>
                  <th>QoQ CHANGE</th>
                  <th>YoY CHANGE</th>
                </>
              )}
              {/* CRITICAL: Respect exact TTM sequential change wording, NEVER QoQ */}
              {data.period_type === 'TTM' && <th>TTM SEQUENTIAL CHANGE</th>}
              <th>STATUS</th>
              <th>AUDIT</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p, idx) => (
              <tr key={idx} className={hoverIndex === idx ? 'row-active' : ''}>
                <td className="td-period-label">
                  <strong>{p.period.display_label || p.period.period_key}</strong>
                  <span className="td-date-sub">{p.period.end_date || p.period.instant_date || ''}</span>
                </td>
                <td className="td-point-value">{formatPointDisplay(p)}</td>
                {data.period_type === 'ANNUAL' && (
                  <td className="td-change">
                    {p.yoy_change !== null && p.yoy_change !== undefined
                      ? `${parseFloat(String(p.yoy_change)) >= 0 ? '+' : ''}${parseFloat(String(p.yoy_change)).toFixed(2)}%`
                      : '—'}
                  </td>
                )}
                {data.period_type === 'QUARTERLY' && (
                  <>
                    <td className="td-change">
                      {p.qoq_change !== null && p.qoq_change !== undefined
                        ? `${parseFloat(String(p.qoq_change)) >= 0 ? '+' : ''}${parseFloat(String(p.qoq_change)).toFixed(2)}%`
                        : '—'}
                    </td>
                    <td className="td-change">
                      {p.yoy_change !== null && p.yoy_change !== undefined
                        ? `${parseFloat(String(p.yoy_change)) >= 0 ? '+' : ''}${parseFloat(String(p.yoy_change)).toFixed(2)}%`
                        : '—'}
                    </td>
                  </>
                )}
                {data.period_type === 'TTM' && (
                  <td className="td-change">
                    {p.ttm_sequential_change !== null && p.ttm_sequential_change !== undefined
                      ? `${parseFloat(String(p.ttm_sequential_change)) >= 0 ? '+' : ''}${parseFloat(String(p.ttm_sequential_change)).toFixed(2)}%`
                      : '—'}
                  </td>
                )}
                <td>
                  <MetricStatusBadge
                    status={p.status as MetricStatus}
                    diagnosticCount={p.diagnostics.length}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="audit-inspect-btn-mini"
                    onClick={() =>
                      onInspectProvenance({
                        metricName: `${metricMeta.label} (${p.period.display_label})`,
                        formattedValue: formatPointDisplay(p),
                        periodLabel: p.period.display_label || p.period.period_key,
                        status: p.status,
                        unit: currentSeries?.unit || '',
                        isDerived: true,
                        provenance: p.provenance,
                        diagnostics: p.diagnostics,
                        category: 'FUNDAMENTAL TREND POINT',
                      })
                    }
                  >
                    PROVENANCE
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
