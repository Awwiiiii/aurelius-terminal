import React, { useMemo, useState } from 'react';
import type { ReturnDistributionSummaryResponse } from '../../types/quantitative';

interface ReturnDistributionInspectorProps {
  data: ReturnDistributionSummaryResponse;
}

export const ReturnDistributionInspector: React.FC<
  ReturnDistributionInspectorProps
> = ({ data }) => {
  const [showGaussian, setShowGaussian] = useState<boolean>(true);
  const [hoveredBin, setHoveredBin] = useState<number | null>(null);

  const stats = data.statistics;
  const quantiles = data.quantiles;
  const bins = data.histogram;

  // Chart dimensions
  const svgWidth = 800;
  const svgHeight = 340;
  const margin = { top: 25, right: 30, bottom: 45, left: 65 };
  const innerWidth = svgWidth - margin.left - margin.right;
  const innerHeight = svgHeight - margin.top - margin.bottom;

  // Numerical ranges
  const minVal = parseFloat(stats.min_value);
  const maxVal = parseFloat(stats.max_value);
  const xSpan = maxVal - minVal || 0.01;

  // Frequency range
  const maxFreq = useMemo(() => {
    let m = 0;
    for (const b of bins) {
      const f = parseFloat(b.frequency);
      if (f > m) m = f;
    }
    return m > 0 ? m * 1.15 : 0.1;
  }, [bins]);

  const xScale = (val: number) => {
    return margin.left + ((val - minVal) / xSpan) * innerWidth;
  };

  const yScale = (freq: number) => {
    return margin.top + innerHeight - (freq / maxFreq) * innerHeight;
  };

  // Compute theoretical Gaussian curve coordinates
  const gaussianPath = useMemo(() => {
    const mean = parseFloat(stats.mean);
    const std = stats.sample_std_dev ? parseFloat(stats.sample_std_dev) : null;
    if (!std || std <= 0 || bins.length === 0) return '';

    const binWidth =
      parseFloat(bins[0].bin_end) - parseFloat(bins[0].bin_start);
    if (binWidth <= 0) return '';

    const points: string[] = [];
    const steps = 120;
    const invSqrt2Pi = 1 / Math.sqrt(2 * Math.PI);

    for (let i = 0; i <= steps; i++) {
      const x = minVal + (i / steps) * xSpan;
      const z = (x - mean) / std;
      // Normal probability density: f(x) = (1 / (s * sqrt(2*pi))) * exp(-0.5 * z^2)
      // Scaled to frequency per bin: f(x) * binWidth
      const density = (invSqrt2Pi / std) * Math.exp(-0.5 * z * z);
      const theoreticalFreq = density * binWidth;

      const px = xScale(x);
      const py = yScale(Math.min(theoreticalFreq, maxFreq * 1.2));
      points.push(`${i === 0 ? 'M' : 'L'} ${px.toFixed(2)} ${py.toFixed(2)}`);
    }
    return points.join(' ');
  }, [stats.mean, stats.sample_std_dev, minVal, xSpan, bins, maxFreq]);

  // Quantile line coordinates
  const q25X = xScale(parseFloat(quantiles.p25));
  const q50X = xScale(parseFloat(quantiles.p50));
  const q75X = xScale(parseFloat(quantiles.p75));

  // Format percentage helper
  const fmtPct = (valStr: string | null | undefined, digits = 2) => {
    if (valStr === null || valStr === undefined) return 'N/A';
    const num = parseFloat(valStr) * 100;
    return `${num >= 0 ? '+' : ''}${num.toFixed(digits)}%`;
  };

  const fmtDec = (valStr: string | null | undefined, digits = 4) => {
    if (valStr === null || valStr === undefined) return 'N/A';
    const num = parseFloat(valStr);
    return num.toFixed(digits);
  };

  return (
    <div className="quant-distribution-panel">
      {/* Moments and Summary Metrics Grid */}
      <div className="quant-moments-grid">
        <div className="quant-moment-card">
          <span className="quant-card-label">OBSERVATIONS (N)</span>
          <span className="quant-card-value highlight">{data.sample_size}</span>
          <span className="quant-card-sub">
            {data.return_type === 'LOG' ? 'Log Returns' : 'Simple Returns'}
          </span>
        </div>

        <div className="quant-moment-card">
          <span className="quant-card-label">MEAN (μ)</span>
          <span className="quant-card-value">{fmtPct(stats.mean, 3)}</span>
          <span className="quant-card-sub">
            Median: {fmtPct(stats.median, 3)}
          </span>
        </div>

        <div className="quant-moment-card">
          <span className="quant-card-label">SAMPLE STD DEV (s)</span>
          <span className="quant-card-value">
            {fmtPct(stats.sample_std_dev, 3)}
          </span>
          <span className="quant-card-sub">
            Pop σ: {fmtPct(stats.population_std_dev, 3)}
          </span>
        </div>

        <div className="quant-moment-card">
          <span className="quant-card-label">SKEWNESS (G₁)</span>
          <span
            className={`quant-card-value ${
              parseFloat(stats.skewness ?? '0') < 0
                ? 'negative'
                : parseFloat(stats.skewness ?? '0') > 0
                  ? 'positive'
                  : ''
            }`}
          >
            {fmtDec(stats.skewness, 3)}
          </span>
          <span className="quant-card-sub">
            {parseFloat(stats.skewness ?? '0') < -0.2
              ? 'Negative (Left-Tail Risk)'
              : parseFloat(stats.skewness ?? '0') > 0.2
                ? 'Positive (Right-Tail)'
                : 'Symmetric'}
          </span>
        </div>

        <div className="quant-moment-card">
          <span className="quant-card-label">EXCESS KURTOSIS (G₂)</span>
          <span
            className={`quant-card-value ${
              parseFloat(stats.excess_kurtosis ?? '0') > 0 ? 'highlight' : ''
            }`}
          >
            {fmtDec(stats.excess_kurtosis, 3)}
          </span>
          <span className="quant-card-sub">
            {parseFloat(stats.excess_kurtosis ?? '0') > 0.5
              ? 'Leptokurtic (Fat Tails)'
              : parseFloat(stats.excess_kurtosis ?? '0') < -0.5
                ? 'Platykurtic'
                : 'Mesokurtic'}
          </span>
        </div>

        <div className="quant-moment-card">
          <span className="quant-card-label">IQR / MAD</span>
          <span className="quant-card-value">{fmtPct(stats.iqr, 3)}</span>
          <span className="quant-card-sub">MAD: {fmtPct(stats.mad, 3)}</span>
        </div>
      </div>

      {/* Directional Observation Breakdown Bar */}
      <div className="quant-directional-bar-wrapper">
        <div className="quant-directional-labels">
          <span className="positive">
            ▲ POSITIVE: {data.positive_count} ({fmtPct(data.positive_pct)})
          </span>
          <span className="neutral">
            ■ ZERO: {data.zero_count} ({fmtPct(data.zero_pct)})
          </span>
          <span className="negative">
            ▼ NEGATIVE: {data.negative_count} ({fmtPct(data.negative_pct)})
          </span>
        </div>
        <div className="quant-directional-progress">
          <div
            className="progress-segment positive"
            style={{ width: `${parseFloat(data.positive_pct) * 100}%` }}
          />
          <div
            className="progress-segment neutral"
            style={{ width: `${parseFloat(data.zero_pct) * 100}%` }}
          />
          <div
            className="progress-segment negative"
            style={{ width: `${parseFloat(data.negative_pct) * 100}%` }}
          />
        </div>
      </div>

      {/* Chart Section */}
      <div className="quant-chart-container">
        <div className="quant-chart-header">
          <div className="quant-chart-title">
            <span>EMPIRICAL RETURN FREQUENCY HISTOGRAM</span>
            <span className="quant-chart-subtitle">
              Freedman-Diaconis Optimal Binning ({bins.length} bins)
            </span>
          </div>
          <div className="quant-chart-controls">
            <button
              type="button"
              className={`quant-toggle-btn ${showGaussian ? 'active' : ''}`}
              onClick={() => setShowGaussian(!showGaussian)}
            >
              {showGaussian ? '◉ GAUSSIAN FIT ON' : '○ GAUSSIAN FIT OFF'}
            </button>
          </div>
        </div>

        <div className="quant-svg-wrapper">
          <svg
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            className="quant-histogram-svg"
            preserveAspectRatio="xMidYMid meet"
          >
            {/* Grid lines */}
            {[0.25, 0.5, 0.75, 1.0].map((frac) => {
              const y =
                margin.top + innerHeight - frac * innerHeight;
              const fVal = (frac * maxFreq * 100).toFixed(1);
              return (
                <g key={`y-grid-${frac}`} className="quant-grid-line">
                  <line
                    x1={margin.left}
                    y1={y}
                    x2={svgWidth - margin.right}
                    y2={y}
                    stroke="rgba(255, 255, 255, 0.07)"
                    strokeDasharray="3 3"
                  />
                  <text
                    x={margin.left - 8}
                    y={y + 4}
                    textAnchor="end"
                    fill="var(--color-text-dim, #71717a)"
                    fontSize="10"
                    fontFamily="monospace"
                  >
                    {fVal}%
                  </text>
                </g>
              );
            })}

            {/* Zero Return Center Line */}
            {minVal <= 0 && maxVal >= 0 && (
              <line
                x1={xScale(0)}
                y1={margin.top}
                x2={xScale(0)}
                y2={margin.top + innerHeight}
                stroke="rgba(255, 255, 255, 0.25)"
                strokeDasharray="4 2"
              />
            )}

            {/* Quantile Markers */}
            <g className="quant-quantile-lines">
              <line
                x1={q25X}
                y1={margin.top}
                x2={q25X}
                y2={margin.top + innerHeight}
                stroke="#38bdf8"
                strokeWidth="1.2"
                strokeDasharray="2 3"
              />
              <line
                x1={q50X}
                y1={margin.top}
                x2={q50X}
                y2={margin.top + innerHeight}
                stroke="#eab308"
                strokeWidth="1.5"
              />
              <line
                x1={q75X}
                y1={margin.top}
                x2={q75X}
                y2={margin.top + innerHeight}
                stroke="#38bdf8"
                strokeWidth="1.2"
                strokeDasharray="2 3"
              />
            </g>

            {/* Histogram Bins */}
            {bins.map((b, idx) => {
              const bStart = parseFloat(b.bin_start);
              const bEnd = parseFloat(b.bin_end);
              const freq = parseFloat(b.frequency);

              const x1 = xScale(bStart);
              const x2 = xScale(bEnd);
              const barWidth = Math.max(1, x2 - x1 - 1);
              const barHeight = (freq / maxFreq) * innerHeight;
              const y = margin.top + innerHeight - barHeight;

              const isPositive = bStart >= 0;
              const isHovered = hoveredBin === idx;

              return (
                <rect
                  key={`bin-${idx}`}
                  x={x1}
                  y={y}
                  width={barWidth}
                  height={barHeight}
                  fill={
                    isHovered
                      ? '#38bdf8'
                      : isPositive
                        ? 'rgba(16, 185, 129, 0.65)'
                        : 'rgba(239, 68, 68, 0.65)'
                  }
                  stroke={isHovered ? '#ffffff' : 'rgba(0, 0, 0, 0.4)'}
                  strokeWidth={isHovered ? 1.5 : 0.5}
                  onMouseEnter={() => setHoveredBin(idx)}
                  onMouseLeave={() => setHoveredBin(null)}
                  className="histogram-bar"
                >
                  <title>{`[${(bStart * 100).toFixed(2)}%, ${(bEnd * 100).toFixed(2)}%)\nCount: ${b.count} (${(freq * 100).toFixed(2)}%)`}</title>
                </rect>
              );
            })}

            {/* Gaussian Curve Overlay */}
            {showGaussian && gaussianPath && (
              <path
                d={gaussianPath}
                fill="none"
                stroke="#f97316"
                strokeWidth="2"
                strokeLinecap="round"
                className="gaussian-curve-path"
              />
            )}

            {/* X-Axis Baseline and Labels */}
            <line
              x1={margin.left}
              y1={margin.top + innerHeight}
              x2={svgWidth - margin.right}
              y2={margin.top + innerHeight}
              stroke="var(--color-border, #333338)"
              strokeWidth="1"
            />
            {[-0.08, -0.06, -0.04, -0.02, 0, 0.02, 0.04, 0.06, 0.08].map(
              (tick) => {
                if (tick < minVal || tick > maxVal) return null;
                const x = xScale(tick);
                return (
                  <g key={`x-tick-${tick}`}>
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
                      {(tick * 100).toFixed(0)}%
                    </text>
                  </g>
                );
              }
            )}
          </svg>

          {/* Hovered Bin Tooltip readout */}
          {hoveredBin !== null && bins[hoveredBin] && (
            <div className="quant-histogram-tooltip">
              <span className="tooltip-range">
                Range: [
                {(
                  parseFloat(bins[hoveredBin].bin_start) * 100
                ).toFixed(2)}
                %,{' '}
                {(
                  parseFloat(bins[hoveredBin].bin_end) * 100
                ).toFixed(2)}
                %)
              </span>
              <span className="tooltip-count">
                Count: <strong>{bins[hoveredBin].count}</strong> (
                {(
                  parseFloat(bins[hoveredBin].frequency) * 100
                ).toFixed(2)}
                %)
              </span>
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="quant-chart-legend">
          <span className="legend-item">
            <span
              className="legend-color-box"
              style={{ background: 'rgba(16, 185, 129, 0.65)' }}
            />
            Positive Returns
          </span>
          <span className="legend-item">
            <span
              className="legend-color-box"
              style={{ background: 'rgba(239, 68, 68, 0.65)' }}
            />
            Negative Returns
          </span>
          <span className="legend-item">
            <span
              className="legend-color-box"
              style={{ background: '#eab308' }}
            />
            Median (P50)
          </span>
          <span className="legend-item">
            <span
              className="legend-color-box"
              style={{ background: '#38bdf8' }}
            />
            IQR Bounds (P25, P75)
          </span>
          {showGaussian && (
            <span className="legend-item">
              <span
                className="legend-color-line"
                style={{ background: '#f97316' }}
              />
              Fitted Normal Curve N(μ, s²)
            </span>
          )}
        </div>
      </div>

      {/* Quantile Ladder Table */}
      <div className="quant-quantiles-panel">
        <h3 className="quant-table-heading">
          EMPIRICAL PERCENTILE LADDER (METHOD 7 LINEAR INTERPOLATION)
        </h3>
        <div className="quant-quantiles-grid">
          {[
            { label: 'P1 (Ext. Left Tail)', val: quantiles.p1, key: 'p1' },
            { label: 'P5 (95% Daily VaR)', val: quantiles.p5, key: 'p5' },
            { label: 'P10', val: quantiles.p10, key: 'p10' },
            { label: 'P25 (Q1)', val: quantiles.p25, key: 'p25', highlight: true },
            {
              label: 'P50 (Median)',
              val: quantiles.p50,
              key: 'p50',
              median: true,
            },
            { label: 'P75 (Q3)', val: quantiles.p75, key: 'p75', highlight: true },
            { label: 'P90', val: quantiles.p90, key: 'p90' },
            { label: 'P95', val: quantiles.p95, key: 'p95' },
            { label: 'P99 (Ext. Right Tail)', val: quantiles.p99, key: 'p99' },
          ].map((q) => (
            <div
              key={q.key}
              className={`quantile-card ${q.highlight ? 'iqr-bound' : ''} ${
                q.median ? 'median-bound' : ''
              }`}
            >
              <span className="quantile-name">{q.label}</span>
              <span className="quantile-value">{fmtPct(q.val, 2)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
