import React, { useEffect, useMemo, useState } from 'react';
import type { HistoricalBarPointResponse } from '../../types/historical';

interface HistoricalChartProps {
  series: HistoricalBarPointResponse[];
  ticker: string;
}

type ChartType = 'CANDLESTICK' | 'LINE';
type SubPanelType = 'VOLUME' | 'DRAWDOWN' | 'ROLLING_VOL';

export const HistoricalChart: React.FC<HistoricalChartProps> = ({
  series,
  ticker,
}) => {
  const [chartType, setChartType] = useState<ChartType>('CANDLESTICK');
  const [subPanel, setSubPanel] = useState<SubPanelType>('VOLUME');
  const [showSMA20, setShowSMA20] = useState<boolean>(true);
  const [showSMA50, setShowSMA50] = useState<boolean>(true);
  const [showSMA200, setShowSMA200] = useState<boolean>(false);
  const [showEMA20, setShowEMA20] = useState<boolean>(false);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // Parse price bounds
  const { minPrice, maxPrice, maxVol, minDD, maxVol20 } = useMemo(() => {
    let minP = Infinity;
    let maxP = -Infinity;
    let maxV = 0;
    let minD = 0;
    let maxV20 = 0;

    for (const p of series) {
      const high = parseFloat(p.high);
      const low = parseFloat(p.low);
      const vol = p.volume;
      const dd = parseFloat(p.drawdown);
      const rVol = p.rolling_vol_20 ? parseFloat(p.rolling_vol_20) : 0;

      if (low < minP) minP = low;
      if (high > maxP) maxP = high;
      if (vol > maxV) maxV = vol;
      if (dd < minD) minD = dd;
      if (rVol > maxV20) maxV20 = rVol;
    }

    if (minP === Infinity) minP = 0;
    if (maxP === -Infinity) maxP = 100;
    if (maxV === 0) maxV = 1;
    if (maxV20 === 0) maxV20 = 0.5;

    // Add 5% padding to price bounds
    const pSpan = maxP - minP;
    const paddedMin = Math.max(0, minP - pSpan * 0.05);
    const paddedMax = maxP + pSpan * 0.05;

    // Add 15% headroom to maxVol20 so the line doesn't clip on top edge
    const paddedMaxVol20 = maxV20 > 0 ? maxV20 * 1.15 : 0.5;

    return {
      minPrice: paddedMin,
      maxPrice: paddedMax,
      maxVol: maxV,
      minDD: Math.min(-0.01, minD),
      maxVol20: paddedMaxVol20,
    };
  }, [series]);

  // Chart dimensions in SVG viewBox coordinate space
  const width = 1000;
  const mainHeight = 360;
  const subHeight = 120;
  const gap = 16;
  const totalHeight = mainHeight + gap + subHeight + 30; // +30 for dates
  const margin = { top: 20, right: 70, bottom: 25, left: 10 };
  const chartWidth = width - margin.left - margin.right;

  // Reset hover crosshair on dataset or ticker changes
  useEffect(() => {
    setHoverIndex(null);
  }, [series, ticker]);

  // Coordinate mappers
  const n = series.length;
  const getX = (idx: number) => {
    if (n <= 1) return margin.left + chartWidth / 2;
    return margin.left + (idx / (n - 1)) * chartWidth;
  };

  const getYPrice = (val: number) => {
    if (maxPrice === minPrice) return margin.top + mainHeight / 2;
    const ratio = (val - minPrice) / (maxPrice - minPrice);
    return margin.top + mainHeight * (1 - ratio);
  };

  const getSubY = (val: number, minVal: number, maxVal: number) => {
    const subTop = margin.top + mainHeight + gap;
    if (maxVal === minVal) return subTop + subHeight / 2;
    const ratio = (val - minVal) / (maxVal - minVal);
    return subTop + subHeight * (1 - ratio);
  };

  // Build SVG Paths
  const linePath = useMemo(() => {
    if (series.length === 0) return '';
    return series
      .map((p, i) => {
        const x = getX(i);
        const y = getYPrice(parseFloat(p.close));
        return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(' ');
  }, [series, minPrice, maxPrice]);

  const makeIndicatorPath = (getter: (p: HistoricalBarPointResponse) => string | null) => {
    let path = '';
    let started = false;
    for (let i = 0; i < series.length; i++) {
      const valStr = getter(series[i]);
      if (valStr !== null) {
        const x = getX(i);
        const y = getYPrice(parseFloat(valStr));
        path += `${!started ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)} `;
        started = true;
      }
    }
    return path;
  };

  const sma20Path = useMemo(() => (showSMA20 ? makeIndicatorPath((p) => p.sma_20) : ''), [series, showSMA20, minPrice, maxPrice]);
  const sma50Path = useMemo(() => (showSMA50 ? makeIndicatorPath((p) => p.sma_50) : ''), [series, showSMA50, minPrice, maxPrice]);
  const sma200Path = useMemo(() => (showSMA200 ? makeIndicatorPath((p) => p.sma_200) : ''), [series, showSMA200, minPrice, maxPrice]);
  const ema20Path = useMemo(() => (showEMA20 ? makeIndicatorPath((p) => p.ema_20) : ''), [series, showEMA20, minPrice, maxPrice]);

  // Underwater Drawdown path
  const drawdownPath = useMemo(() => {
    if (series.length === 0) return '';
    const zeroY = getSubY(0, minDD, 0);

    let path = `M ${getX(0)} ${zeroY}`;
    series.forEach((p, i) => {
      const x = getX(i);
      const y = getSubY(parseFloat(p.drawdown), minDD, 0);
      path += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
    });
    path += ` L ${getX(series.length - 1)} ${zeroY} Z`;
    return path;
  }, [series, minDD]);

  // Rolling Volatility path and area (safely handles null warm-up observations)
  const { rollingVolPath, rollingVolAreaPath } = useMemo(() => {
    if (series.length === 0) return { rollingVolPath: '', rollingVolAreaPath: '' };

    let path = '';
    let areaPath = '';
    let firstX: number | null = null;
    let lastX: number | null = null;
    const zeroY = getSubY(0, 0, maxVol20);

    for (let i = 0; i < series.length; i++) {
      const p = series[i];
      if (p.rolling_vol_20 !== null) {
        const val = parseFloat(p.rolling_vol_20);
        if (!isNaN(val)) {
          const x = getX(i);
          const y = getSubY(val, 0, maxVol20);
          if (firstX === null) {
            firstX = x;
            path += `M ${x.toFixed(1)} ${y.toFixed(1)}`;
            areaPath += `M ${x.toFixed(1)} ${zeroY.toFixed(1)} L ${x.toFixed(1)} ${y.toFixed(1)}`;
          } else {
            path += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
            areaPath += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
          }
          lastX = x;
        }
      }
    }

    if (firstX !== null && lastX !== null) {
      areaPath += ` L ${lastX.toFixed(1)} ${zeroY.toFixed(1)} Z`;
    }

    return { rollingVolPath: path, rollingVolAreaPath: areaPath };
  }, [series, maxVol20]);

  // Active hover bar point
  const activePoint = hoverIndex !== null && hoverIndex >= 0 && hoverIndex < series.length ? series[hoverIndex] : null;

  // Handle mouse move over SVG
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (series.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * width;
    const clampedX = Math.max(margin.left, Math.min(width - margin.right, svgX));
    const ratio = (clampedX - margin.left) / chartWidth;
    const rawIdx = Math.round(ratio * (series.length - 1));
    const idx = Math.max(0, Math.min(series.length - 1, rawIdx));
    setHoverIndex(idx);
  };

  const handleMouseLeave = () => {
    setHoverIndex(null);
  };

  // Price grid ticks
  const priceTicks = useMemo(() => {
    const ticks = [];
    const steps = 5;
    for (let i = 0; i <= steps; i++) {
      const val = minPrice + (i / steps) * (maxPrice - minPrice);
      const y = getYPrice(val);
      ticks.push({ val: val.toFixed(2), y });
    }
    return ticks;
  }, [minPrice, maxPrice]);

  return (
    <div className="historical-chart-container">
      {/* Chart Toolbar */}
      <div className="chart-toolbar">
        <div className="chart-toolbar-group">
          <span className="ticker-badge" style={{ marginRight: '8px' }}>
            {ticker}
          </span>
          <span className="toolbar-label">SERIES:</span>
          <button
            type="button"
            className={`toolbar-toggle ${chartType === 'CANDLESTICK' ? 'active' : ''}`}
            onClick={() => setChartType('CANDLESTICK')}
          >
            CANDLES
          </button>
          <button
            type="button"
            className={`toolbar-toggle ${chartType === 'LINE' ? 'active' : ''}`}
            onClick={() => setChartType('LINE')}
          >
            CLOSE LINE
          </button>
        </div>

        <div className="chart-toolbar-group">
          <span className="toolbar-label">OVERLAYS:</span>
          <button
            type="button"
            className={`toolbar-toggle sma20 ${showSMA20 ? 'active' : ''}`}
            onClick={() => setShowSMA20(!showSMA20)}
          >
            SMA 20
          </button>
          <button
            type="button"
            className={`toolbar-toggle sma50 ${showSMA50 ? 'active' : ''}`}
            onClick={() => setShowSMA50(!showSMA50)}
          >
            SMA 50
          </button>
          <button
            type="button"
            className={`toolbar-toggle sma200 ${showSMA200 ? 'active' : ''}`}
            onClick={() => setShowSMA200(!showSMA200)}
          >
            SMA 200
          </button>
          <button
            type="button"
            className={`toolbar-toggle ema20 ${showEMA20 ? 'active' : ''}`}
            onClick={() => setShowEMA20(!showEMA20)}
          >
            EMA 20
          </button>
        </div>

        <div className="chart-toolbar-group">
          <span className="toolbar-label">SUB-PANEL:</span>
          <button
            type="button"
            className={`toolbar-toggle ${subPanel === 'VOLUME' ? 'active' : ''}`}
            onClick={() => setSubPanel('VOLUME')}
          >
            VOLUME
          </button>
          <button
            type="button"
            className={`toolbar-toggle ${subPanel === 'DRAWDOWN' ? 'active' : ''}`}
            onClick={() => setSubPanel('DRAWDOWN')}
          >
            UNDERWATER DD
          </button>
          <button
            type="button"
            className={`toolbar-toggle ${subPanel === 'ROLLING_VOL' ? 'active' : ''}`}
            onClick={() => setSubPanel('ROLLING_VOL')}
          >
            ROLLING VOL
          </button>
        </div>
      </div>

      {/* Hover Telemetry HUD */}
      <div className="chart-hud">
        {activePoint ? (
          <div className="hud-content">
            <span className="hud-date">{activePoint.date}</span>
            <span className="hud-item">
              O: <strong>${activePoint.open}</strong>
            </span>
            <span className="hud-item">
              H: <strong>${activePoint.high}</strong>
            </span>
            <span className="hud-item">
              L: <strong>${activePoint.low}</strong>
            </span>
            <span className="hud-item">
              C: <strong>${activePoint.close}</strong>
            </span>
            <span className="hud-item">
              Adj: <strong>${activePoint.adj_close}</strong>
            </span>
            {activePoint.daily_return && (
              <span
                className={`hud-item ${
                  parseFloat(activePoint.daily_return) >= 0
                    ? 'positive'
                    : 'negative'
                }`}
              >
                Ret:{' '}
                <strong>
                  {parseFloat(activePoint.daily_return) >= 0 ? '+' : ''}
                  {(parseFloat(activePoint.daily_return) * 100).toFixed(2)}%
                </strong>
              </span>
            )}
            <span className="hud-item">
              DD:{' '}
              <strong className="negative">
                {(parseFloat(activePoint.drawdown) * 100).toFixed(2)}%
              </strong>
            </span>
            <span className="hud-item">
              Vol: <strong>{activePoint.volume.toLocaleString()}</strong>
            </span>
            {showSMA20 && activePoint.sma_20 && (
              <span className="hud-item sma20-text">
                SMA20: <strong>${activePoint.sma_20}</strong>
              </span>
            )}
            {showSMA50 && activePoint.sma_50 && (
              <span className="hud-item sma50-text">
                SMA50: <strong>${activePoint.sma_50}</strong>
              </span>
            )}
            {showSMA200 && activePoint.sma_200 && (
              <span className="hud-item sma200-text">
                SMA200: <strong>${activePoint.sma_200}</strong>
              </span>
            )}
            {showEMA20 && activePoint.ema_20 && (
              <span className="hud-item ema20-text">
                EMA20: <strong>${activePoint.ema_20}</strong>
              </span>
            )}
            {subPanel === 'ROLLING_VOL' && (
              <span className="hud-item" style={{ color: '#fbbf24' }}>
                σ20:{' '}
                <strong>
                  {activePoint.rolling_vol_20 !== null
                    ? `${(parseFloat(activePoint.rolling_vol_20) * 100).toFixed(2)}%`
                    : 'WARM-UP (<20 returns)'}
                </strong>
              </span>
            )}
          </div>
        ) : (
          <div className="hud-placeholder">
            <span>Hover cursor over time series to inspect crosshair session telemetry.</span>
          </div>
        )}
      </div>

      {/* Main SVG Canvas */}
      <svg
        className="historical-svg"
        viewBox={`0 0 ${width} ${totalHeight}`}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <defs>
          <clipPath id="mainPanelClip">
            <rect
              x={margin.left}
              y={margin.top}
              width={chartWidth}
              height={mainHeight}
            />
          </clipPath>
          <clipPath id="subPanelClip">
            <rect
              x={margin.left}
              y={margin.top + mainHeight + gap}
              width={chartWidth}
              height={subHeight}
            />
          </clipPath>
          <linearGradient id="drawdownGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(248, 113, 113, 0.4)" />
            <stop offset="100%" stopColor="rgba(239, 68, 68, 0.05)" />
          </linearGradient>
          <linearGradient id="rollingVolGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(251, 191, 36, 0.35)" />
            <stop offset="100%" stopColor="rgba(251, 191, 36, 0.02)" />
          </linearGradient>
        </defs>

        {/* Background Grid & Axis Lines */}
        <rect
          x={margin.left}
          y={margin.top}
          width={chartWidth}
          height={mainHeight}
          fill="rgba(10, 15, 29, 0.7)"
          stroke="rgba(255, 255, 255, 0.08)"
        />
        <rect
          x={margin.left}
          y={margin.top + mainHeight + gap}
          width={chartWidth}
          height={subHeight}
          fill="rgba(10, 15, 29, 0.7)"
          stroke="rgba(255, 255, 255, 0.08)"
        />

        {/* Price Horizontal Grid Lines */}
        {priceTicks.map((t, idx) => (
          <g key={idx}>
            <line
              x1={margin.left}
              y1={t.y}
              x2={margin.left + chartWidth}
              y2={t.y}
              stroke="rgba(255, 255, 255, 0.05)"
              strokeDasharray="3 3"
            />
            <text
              x={margin.left + chartWidth + 8}
              y={t.y + 4}
              fill="rgba(148, 163, 184, 0.8)"
              fontSize="11"
              fontFamily="monospace"
            >
              ${t.val}
            </text>
          </g>
        ))}

        {/* Main Chart Panel (Hardware Vector Clipped) */}
        <g clipPath="url(#mainPanelClip)">
          {/* Line Chart */}
          {chartType === 'LINE' && (
            <path
              d={linePath}
              fill="none"
              stroke="#38bdf8"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Candlestick Chart */}
          {chartType === 'CANDLESTICK' && (
            <g className="candles-group">
              {series.map((p, i) => {
                const x = getX(i);
                const o = parseFloat(p.open);
                const c = parseFloat(p.close);
                const h = parseFloat(p.high);
                const l = parseFloat(p.low);

                const yO = getYPrice(o);
                const yC = getYPrice(c);
                const yH = getYPrice(h);
                const yL = getYPrice(l);

                const isUp = c >= o;
                const candleColor = isUp ? '#34d399' : '#f87171';
                const candleWidth = Math.max(1.5, Math.min(10, (chartWidth / n) * 0.7));
                const topY = Math.min(yO, yC);
                const bodyHeight = Math.max(1, Math.abs(yO - yC));

                return (
                  <g key={p.date} className="candle">
                    {/* High-Low Wick */}
                    <line
                      x1={x}
                      y1={yH}
                      x2={x}
                      y2={yL}
                      stroke={candleColor}
                      strokeWidth="1"
                    />
                    {/* Real Body */}
                    <rect
                      x={x - candleWidth / 2}
                      y={topY}
                      width={candleWidth}
                      height={bodyHeight}
                      fill={candleColor}
                      stroke={candleColor}
                      strokeWidth="0.5"
                    />
                  </g>
                );
              })}
            </g>
          )}

          {/* Overlay Paths */}
          {showSMA20 && sma20Path && (
            <path
              d={sma20Path}
              fill="none"
              stroke="#06b6d4"
              strokeWidth="1.5"
              strokeDasharray="none"
            />
          )}
          {showSMA50 && sma50Path && (
            <path
              d={sma50Path}
              fill="none"
              stroke="#f59e0b"
              strokeWidth="1.5"
              strokeDasharray="none"
            />
          )}
          {showSMA200 && sma200Path && (
            <path
              d={sma200Path}
              fill="none"
              stroke="#a855f7"
              strokeWidth="1.5"
              strokeDasharray="none"
            />
          )}
          {showEMA20 && ema20Path && (
            <path
              d={ema20Path}
              fill="none"
              stroke="#10b981"
              strokeWidth="1.5"
              strokeDasharray="none"
            />
          )}
        </g>

        {/* Sub-Panel Renderings (Hardware Vector Clipped) */}
        <g clipPath="url(#subPanelClip)">
          {subPanel === 'VOLUME' && (
            <g className="volume-bars">
              {series.map((p, i) => {
                const x = getX(i);
                const vol = p.volume;
                const y = getSubY(vol, 0, maxVol);
                const subBottom = margin.top + mainHeight + gap + subHeight;
                const barH = Math.max(1, subBottom - y);
                const isUp = parseFloat(p.close) >= parseFloat(p.open);
                const col = isUp ? 'rgba(52, 211, 153, 0.4)' : 'rgba(248, 113, 113, 0.4)';
                const barWidth = Math.max(1, Math.min(8, (chartWidth / n) * 0.7));

                return (
                  <rect
                    key={p.date}
                    x={x - barWidth / 2}
                    y={y}
                    width={barWidth}
                    height={barH}
                    fill={col}
                  />
                );
              })}
            </g>
          )}

          {subPanel === 'DRAWDOWN' && (
            <g className="underwater-dd">
              <path d={drawdownPath} fill="url(#drawdownGrad)" stroke="#ef4444" strokeWidth="1.5" />
              <line
                x1={margin.left}
                y1={getSubY(0, minDD, 0)}
                x2={margin.left + chartWidth}
                y2={getSubY(0, minDD, 0)}
                stroke="rgba(255, 255, 255, 0.3)"
                strokeDasharray="2 2"
              />
            </g>
          )}

          {subPanel === 'ROLLING_VOL' && (
            <g className="rolling-vol">
              {rollingVolAreaPath && (
                <path d={rollingVolAreaPath} fill="url(#rollingVolGrad)" />
              )}
              {rollingVolPath && (
                <path
                  d={rollingVolPath}
                  fill="none"
                  stroke="#fbbf24"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              )}
            </g>
          )}
        </g>

        {/* Sub-Panel Grid Lines and Y-Axis Ticks */}
        {subPanel === 'VOLUME' && (
          <g className="sub-panel-ticks">
            <line
              x1={margin.left}
              y1={getSubY(maxVol / 2, 0, maxVol)}
              x2={margin.left + chartWidth}
              y2={getSubY(maxVol / 2, 0, maxVol)}
              stroke="rgba(255, 255, 255, 0.05)"
              strokeDasharray="3 3"
            />
            <text
              x={margin.left + chartWidth + 8}
              y={getSubY(maxVol, 0, maxVol) + 4}
              fill="rgba(148, 163, 184, 0.7)"
              fontSize="10"
              fontFamily="monospace"
            >
              {(maxVol / 1000000).toFixed(1)}M Vol
            </text>
            <text
              x={margin.left + chartWidth + 8}
              y={getSubY(maxVol / 2, 0, maxVol) + 4}
              fill="rgba(148, 163, 184, 0.5)"
              fontSize="9"
              fontFamily="monospace"
            >
              {(maxVol / 2000000).toFixed(1)}M
            </text>
            <text
              x={margin.left + chartWidth + 8}
              y={getSubY(0, 0, maxVol)}
              fill="rgba(148, 163, 184, 0.5)"
              fontSize="9"
              fontFamily="monospace"
            >
              0
            </text>
          </g>
        )}

        {subPanel === 'DRAWDOWN' && (
          <g className="sub-panel-ticks">
            <line
              x1={margin.left}
              y1={getSubY(minDD / 2, minDD, 0)}
              x2={margin.left + chartWidth}
              y2={getSubY(minDD / 2, minDD, 0)}
              stroke="rgba(255, 255, 255, 0.05)"
              strokeDasharray="3 3"
            />
            <text
              x={margin.left + chartWidth + 8}
              y={getSubY(0, minDD, 0) + 4}
              fill="rgba(148, 163, 184, 0.7)"
              fontSize="10"
              fontFamily="monospace"
            >
              0.0% DD
            </text>
            <text
              x={margin.left + chartWidth + 8}
              y={getSubY(minDD / 2, minDD, 0) + 4}
              fill="rgba(148, 163, 184, 0.5)"
              fontSize="9"
              fontFamily="monospace"
            >
              {(minDD * 50).toFixed(1)}%
            </text>
            <text
              x={margin.left + chartWidth + 8}
              y={getSubY(minDD, minDD, 0)}
              fill="rgba(148, 163, 184, 0.5)"
              fontSize="9"
              fontFamily="monospace"
            >
              {(minDD * 100).toFixed(1)}%
            </text>
          </g>
        )}

        {subPanel === 'ROLLING_VOL' && (
          <g className="sub-panel-ticks">
            <line
              x1={margin.left}
              y1={getSubY(maxVol20 / 2, 0, maxVol20)}
              x2={margin.left + chartWidth}
              y2={getSubY(maxVol20 / 2, 0, maxVol20)}
              stroke="rgba(255, 255, 255, 0.05)"
              strokeDasharray="3 3"
            />
            <text
              x={margin.left + chartWidth + 8}
              y={getSubY(maxVol20, 0, maxVol20) + 4}
              fill="rgba(251, 191, 36, 0.85)"
              fontSize="10"
              fontFamily="monospace"
              fontWeight="600"
            >
              {(maxVol20 * 100).toFixed(1)}% σ
            </text>
            <text
              x={margin.left + chartWidth + 8}
              y={getSubY(maxVol20 / 2, 0, maxVol20) + 4}
              fill="rgba(148, 163, 184, 0.5)"
              fontSize="9"
              fontFamily="monospace"
            >
              {(maxVol20 * 50).toFixed(1)}%
            </text>
            <text
              x={margin.left + chartWidth + 8}
              y={getSubY(0, 0, maxVol20)}
              fill="rgba(148, 163, 184, 0.5)"
              fontSize="9"
              fontFamily="monospace"
            >
              0.0%
            </text>
          </g>
        )}

        {/* Interactive Crosshair */}
        {hoverIndex !== null && activePoint && (
          <g className="crosshair-group">
            {/* Vertical Crosshair Line */}
            <line
              x1={getX(hoverIndex)}
              y1={margin.top}
              x2={getX(hoverIndex)}
              y2={margin.top + mainHeight + gap + subHeight}
              stroke="rgba(255, 255, 255, 0.4)"
              strokeDasharray="2 2"
            />
            {/* Horizontal Price Crosshair Line */}
            <line
              x1={margin.left}
              y1={getYPrice(parseFloat(activePoint.close))}
              x2={margin.left + chartWidth}
              y2={getYPrice(parseFloat(activePoint.close))}
              stroke="rgba(255, 255, 255, 0.3)"
              strokeDasharray="2 2"
            />
            {/* Crosshair Point Dot */}
            <circle
              cx={getX(hoverIndex)}
              cy={getYPrice(parseFloat(activePoint.close))}
              r="4"
              fill="#38bdf8"
              stroke="#0f172a"
              strokeWidth="2"
            />
          </g>
        )}

        {/* Date Labels along bottom */}
        {series.length > 0 && (
          <g className="date-labels">
            <text
              x={margin.left}
              y={totalHeight - 6}
              fill="rgba(148, 163, 184, 0.8)"
              fontSize="10"
              fontFamily="monospace"
            >
              {series[0].date}
            </text>
            <text
              x={margin.left + chartWidth / 2}
              y={totalHeight - 6}
              fill="rgba(148, 163, 184, 0.8)"
              fontSize="10"
              fontFamily="monospace"
              textAnchor="middle"
            >
              {series[Math.floor(series.length / 2)].date}
            </text>
            <text
              x={margin.left + chartWidth}
              y={totalHeight - 6}
              fill="rgba(148, 163, 184, 0.8)"
              fontSize="10"
              fontFamily="monospace"
              textAnchor="end"
            >
              {series[series.length - 1].date}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
};
