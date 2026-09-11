import React, { useMemo, useState } from 'react';
import type {
  QuantitativeMetricType,
  RollingQuantitativeSeriesResponse,
} from '../../types/quantitative';

interface RollingCorrelationChartProps {
  data: RollingQuantitativeSeriesResponse | null;
  isLoading: boolean;
  metric: QuantitativeMetricType;
  windowSize: number;
  tickerA: string;
  tickerB: string;
  onChangeMetric: (m: QuantitativeMetricType) => void;
  onChangeWindow: (w: number) => void;
  onChangeTickerB: (t: string) => void;
  onRefresh: () => void;
}

export const RollingCorrelationChart: React.FC<
  RollingCorrelationChartProps
> = ({
  data,
  isLoading,
  metric,
  windowSize,
  tickerA,
  tickerB,
  onChangeMetric,
  onChangeWindow,
  onChangeTickerB,
  onRefresh,
}) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const series = data?.series ?? [];
  const validPoints = series.filter((p) => p.value !== null);

  // SVG dimensions
  const svgWidth = 800;
  const svgHeight = 320;
  const margin = { top: 25, right: 30, bottom: 40, left: 65 };
  const innerWidth = svgWidth - margin.left - margin.right;
  const innerHeight = svgHeight - margin.top - margin.bottom;

  // Compute domain bounds
  const { minVal, maxVal } = useMemo(() => {
    if (validPoints.length === 0) {
      if (metric === 'CORRELATION') return { minVal: -1.0, maxVal: 1.0 };
      return { minVal: 0, maxVal: 0.05 };
    }

    let min = Infinity;
    let max = -Infinity;
    for (const p of validPoints) {
      const v = parseFloat(p.value!);
      if (v < min) min = v;
      if (v > max) max = v;
    }

    if (metric === 'CORRELATION') {
      return {
        minVal: Math.min(-0.2, min - 0.1),
        maxVal: Math.max(0.2, max + 0.1),
      };
    }

    const pad = (max - min) * 0.15 || 0.01;
    return {
      minVal: Math.max(0, min - pad),
      maxVal: max + pad,
    };
  }, [validPoints, metric]);

  const ySpan = maxVal - minVal || 1.0;

  const xScale = (idx: number) => {
    if (series.length <= 1) return margin.left;
    return margin.left + (idx / (series.length - 1)) * innerWidth;
  };

  const yScale = (val: number) => {
    return margin.top + innerHeight - ((val - minVal) / ySpan) * innerHeight;
  };

  // Build SVG polyline/path string
  const linePath = useMemo(() => {
    if (series.length === 0) return '';
    const segments: string[] = [];
    let isDrawing = false;

    for (let i = 0; i < series.length; i++) {
      const valStr = series[i].value;
      if (valStr === null) {
        isDrawing = false;
        continue;
      }
      const val = parseFloat(valStr);
      const x = xScale(i);
      const y = yScale(val);

      if (!isDrawing) {
        segments.push(`M ${x.toFixed(2)} ${y.toFixed(2)}`);
        isDrawing = true;
      } else {
        segments.push(`L ${x.toFixed(2)} ${y.toFixed(2)}`);
      }
    }
    return segments.join(' ');
  }, [series, minVal, ySpan]);

  // Area under the line (closed polygon)
  const areaPath = useMemo(() => {
    if (series.length === 0 || !linePath) return '';
    const baselineY = yScale(Math.max(minVal, 0));
    let firstX = margin.left;
    let lastX = margin.left + innerWidth;

    for (let i = 0; i < series.length; i++) {
      if (series[i].value !== null) {
        firstX = xScale(i);
        break;
      }
    }
    for (let i = series.length - 1; i >= 0; i--) {
      if (series[i].value !== null) {
        lastX = xScale(i);
        break;
      }
    }

    return `${linePath} L ${lastX.toFixed(2)} ${baselineY.toFixed(2)} L ${firstX.toFixed(2)} ${baselineY.toFixed(2)} Z`;
  }, [linePath, series, minVal, ySpan]);

  // Y-axis grid ticks
  const yTicks = useMemo(() => {
    const ticks: number[] = [];
    const stepCount = 5;
    for (let i = 0; i <= stepCount; i++) {
      ticks.push(minVal + (i / stepCount) * ySpan);
    }
    return ticks;
  }, [minVal, ySpan]);

  return (
    <div className="quant-rolling-panel">
      {/* Configuration Toolbar */}
      <div className="quant-rolling-toolbar">
        <div className="quant-rolling-param-group">
          <span className="quant-toolbar-label">METRIC:</span>
          <div className="quant-toggle-buttons">
            <button
              type="button"
              className={`quant-toggle-btn ${
                metric === 'VOLATILITY' ? 'active' : ''
              }`}
              onClick={() => onChangeMetric('VOLATILITY')}
            >
              VOLATILITY (s)
            </button>
            <button
              type="button"
              className={`quant-toggle-btn ${
                metric === 'CORRELATION' ? 'active' : ''
              }`}
              onClick={() => onChangeMetric('CORRELATION')}
            >
              CORRELATION (r)
            </button>
            <button
              type="button"
              className={`quant-toggle-btn ${
                metric === 'MEAN' ? 'active' : ''
              }`}
              onClick={() => onChangeMetric('MEAN')}
            >
              MEAN (μ)
            </button>
          </div>
        </div>

        <div className="quant-rolling-param-group">
          <span className="quant-toolbar-label">WINDOW:</span>
          <div className="quant-toggle-buttons">
            {[20, 60, 120].map((w) => (
              <button
                key={`w-${w}`}
                type="button"
                className={`quant-toggle-btn ${
                  windowSize === w ? 'active' : ''
                }`}
                onClick={() => onChangeWindow(w)}
              >
                {w}D
              </button>
            ))}
          </div>
        </div>

        {metric === 'CORRELATION' && (
          <div className="quant-rolling-param-group">
            <label className="quant-toolbar-label" htmlFor="quant-compare-ticker-input">
              COMPARE TICKER:
            </label>
            <div className="quant-input-group">
              <input
                id="quant-compare-ticker-input"
                type="text"
                value={tickerB}
                onChange={(e) => onChangeTickerB(e.target.value.toUpperCase())}
                placeholder="e.g. SPY"
                className="quant-text-input-compact"
              />
              <button
                type="button"
                className="quant-submit-btn-compact"
                onClick={onRefresh}
              >
                UPDATE
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Chart Section */}
      <div className="quant-chart-container">
        <div className="quant-chart-header">
          <div className="quant-chart-title">
            <span>
              ROLLING {metric} ({windowSize}-DAY RETURN WINDOW)
            </span>
            <span className="quant-chart-subtitle">
              {metric === 'CORRELATION'
                ? `${tickerA} vs ${tickerB} (Zero-indexed warm-up)`
                : `${tickerA} Daily Returns`}
            </span>
          </div>
        </div>

        <div className="quant-svg-wrapper">
          {isLoading ? (
            <div className="quant-loading-indicator">
              CALCULATING ROLLING SERIES...
            </div>
          ) : series.length === 0 ? (
            <div className="quant-empty-state">
              No rolling series data available for the selected parameters.
            </div>
          ) : (
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              className="quant-rolling-svg"
              preserveAspectRatio="xMidYMid meet"
              onMouseMove={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                const mouseX =
                  ((e.clientX - rect.left) / rect.width) * svgWidth;
                if (
                  mouseX >= margin.left &&
                  mouseX <= svgWidth - margin.right
                ) {
                  const frac = (mouseX - margin.left) / innerWidth;
                  const idx = Math.min(
                    series.length - 1,
                    Math.max(0, Math.round(frac * (series.length - 1)))
                  );
                  setHoverIndex(idx);
                }
              }}
              onMouseLeave={() => setHoverIndex(null)}
            >
              <defs>
                <clipPath id="rolling-chart-clip">
                  <rect
                    x={margin.left}
                    y={margin.top}
                    width={innerWidth}
                    height={innerHeight}
                  />
                </clipPath>
                <linearGradient
                  id="rolling-area-grad"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="0%"
                    stopColor="#38bdf8"
                    stopOpacity="0.35"
                  />
                  <stop
                    offset="100%"
                    stopColor="#38bdf8"
                    stopOpacity="0.0"
                  />
                </linearGradient>
              </defs>

              {/* Y-Axis Grid Lines */}
              {yTicks.map((val) => {
                const y = yScale(val);
                return (
                  <g key={`y-tick-${val}`}>
                    <line
                      x1={margin.left}
                      y1={y}
                      x2={svgWidth - margin.right}
                      y2={y}
                      stroke="rgba(255, 255, 255, 0.08)"
                      strokeDasharray="2 3"
                    />
                    <text
                      x={margin.left - 8}
                      y={y + 4}
                      textAnchor="end"
                      fill="var(--color-text-dim, #71717a)"
                      fontSize="10"
                      fontFamily="monospace"
                    >
                      {metric === 'CORRELATION'
                        ? val.toFixed(2)
                        : `${(val * 100).toFixed(2)}%`}
                    </text>
                  </g>
                );
              })}

              {/* Zero Reference Line */}
              {minVal <= 0 && maxVal >= 0 && (
                <line
                  x1={margin.left}
                  y1={yScale(0)}
                  x2={svgWidth - margin.right}
                  y2={yScale(0)}
                  stroke="rgba(255, 255, 255, 0.25)"
                  strokeDasharray="4 2"
                />
              )}

              {/* Shaded Area and Line */}
              <g clipPath="url(#rolling-chart-clip)">
                {areaPath && (
                  <path d={areaPath} fill="url(#rolling-area-grad)" />
                )}
                {linePath && (
                  <path
                    d={linePath}
                    fill="none"
                    stroke="#38bdf8"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                )}
              </g>

              {/* Hover Crosshair and Point */}
              {hoverIndex !== null && series[hoverIndex] && (
                <g className="quant-hover-group">
                  <line
                    x1={xScale(hoverIndex)}
                    y1={margin.top}
                    x2={xScale(hoverIndex)}
                    y2={margin.top + innerHeight}
                    stroke="rgba(255, 255, 255, 0.4)"
                    strokeDasharray="3 3"
                  />
                  {series[hoverIndex].value !== null && (
                    <circle
                      cx={xScale(hoverIndex)}
                      cy={yScale(
                        parseFloat(series[hoverIndex].value!)
                      )}
                      r="4"
                      fill="#38bdf8"
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                  )}
                </g>
              )}

              {/* X-Axis Baseline */}
              <line
                x1={margin.left}
                y1={margin.top + innerHeight}
                x2={svgWidth - margin.right}
                y2={margin.top + innerHeight}
                stroke="var(--color-border, #333338)"
                strokeWidth="1"
              />

              {/* X-Axis Date Labels */}
              {series.length > 0 &&
                [0, 0.25, 0.5, 0.75, 1.0].map((frac) => {
                  const idx = Math.min(
                    series.length - 1,
                    Math.round(frac * (series.length - 1))
                  );
                  const pt = series[idx];
                  if (!pt) return null;
                  const x = xScale(idx);
                  return (
                    <g key={`x-date-${idx}`}>
                      <line
                        x1={x}
                        y1={margin.top + innerHeight}
                        x2={x}
                        y2={margin.top + innerHeight + 5}
                        stroke="rgba(255, 255, 255, 0.3)"
                      />
                      <text
                        x={x}
                        y={margin.top + innerHeight + 18}
                        textAnchor="middle"
                        fill="var(--color-text-dim, #71717a)"
                        fontSize="10"
                        fontFamily="monospace"
                      >
                        {pt.date}
                      </text>
                    </g>
                  );
                })}
            </svg>
          )}

          {/* Hover Readout Tooltip */}
          {hoverIndex !== null && series[hoverIndex] && (
            <div className="quant-histogram-tooltip">
              <span className="tooltip-range">
                Date: {series[hoverIndex].date}
              </span>
              <span className="tooltip-count">
                Value:{' '}
                <strong>
                  {series[hoverIndex].value !== null
                    ? metric === 'CORRELATION'
                      ? parseFloat(series[hoverIndex].value!).toFixed(4)
                      : `${(
                          parseFloat(series[hoverIndex].value!) * 100
                        ).toFixed(3)}%`
                    : 'Unpopulated (Warm-up)'}
                </strong>
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
