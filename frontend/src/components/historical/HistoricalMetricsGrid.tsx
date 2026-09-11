import React from 'react';
import type { HistoricalAnalysisResponse } from '../../types/historical';

interface HistoricalMetricsGridProps {
  analysis: HistoricalAnalysisResponse;
}

export const HistoricalMetricsGrid: React.FC<HistoricalMetricsGridProps> = ({
  analysis,
}) => {
  const { returns, volatility, drawdowns, extremes, benchmark_comparison } =
    analysis;

  const adjReturnNum = parseFloat(returns.adjusted_price_return) * 100;
  const isReturnPositive = adjReturnNum >= 0;

  const cagrNum = returns.cagr ? parseFloat(returns.cagr) * 100 : null;
  const winRateNum = returns.win_rate ? parseFloat(returns.win_rate) * 100 : null;

  const annVolNum = parseFloat(volatility.annualized_volatility) * 100;
  const dailyVolNum = parseFloat(volatility.daily_volatility) * 100;

  const maxDdNum = parseFloat(drawdowns.max_drawdown) * 100;
  const currentDdNum = parseFloat(drawdowns.current_drawdown) * 100;

  return (
    <div className="historical-metrics-grid">
      {/* 1. Adjusted Price Return */}
      <div className="metric-card">
        <div className="metric-header">
          <span className="metric-label">ADJUSTED PRICE RETURN</span>
          <span className="metric-badge">ADJ CLOSE</span>
        </div>
        <div
          className={`metric-value-large ${
            isReturnPositive ? 'positive' : 'negative'
          }`}
        >
          {isReturnPositive ? '+' : ''}
          {adjReturnNum.toFixed(2)}%
        </div>
        <div className="metric-subtext">
          <span>Mean Daily: {(parseFloat(returns.mean_daily_return) * 100).toFixed(3)}%</span>
          <span className="methodology-hint">Split/Dividend Proxy</span>
        </div>
      </div>

      {/* 2. Calendar CAGR */}
      <div className="metric-card">
        <div className="metric-header">
          <span className="metric-label">CALENDAR-TIME CAGR</span>
          <span className="metric-badge">COMPOUNDED</span>
        </div>
        <div className="metric-value-large">
          {cagrNum !== null ? `${cagrNum >= 0 ? '+' : ''}${cagrNum.toFixed(2)}%` : 'N/A'}
        </div>
        <div className="metric-subtext">
          <span>{cagrNum !== null ? '365.2425 Day Basis' : 'Requires ≥ 365 Days'}</span>
          <span className="methodology-hint">Elapsed Calendar Time</span>
        </div>
      </div>

      {/* 3. Win Rate */}
      <div className="metric-card">
        <div className="metric-header">
          <span className="metric-label">WIN RATE (DAILY)</span>
          <span className="metric-badge">{returns.positive_days + returns.negative_days} SESSIONS</span>
        </div>
        <div className="metric-value-large">
          {winRateNum !== null ? `${winRateNum.toFixed(1)}%` : 'N/A'}
        </div>
        <div className="metric-subtext">
          <span className="session-counts">
            <span className="pos">+{returns.positive_days}</span> /{' '}
            <span className="neg">-{returns.negative_days}</span> /{' '}
            <span className="zero">={returns.zero_days}</span>
          </span>
          <span className="methodology-hint">Zeros Excluded</span>
        </div>
      </div>

      {/* 4. Realized Volatility */}
      <div className="metric-card">
        <div className="metric-header">
          <span className="metric-label">REALIZED VOLATILITY</span>
          <span className="metric-badge">ANNUALIZED</span>
        </div>
        <div className="metric-value-large">{annVolNum.toFixed(1)}%</div>
        <div className="metric-subtext">
          <span>Daily σ: {dailyVolNum.toFixed(2)}%</span>
          <span className="methodology-hint">Bessel N-1 (√252)</span>
        </div>
      </div>

      {/* 5. Max Drawdown */}
      <div className="metric-card">
        <div className="metric-header">
          <span className="metric-label">MAX DRAWDOWN</span>
          <span
            className={`metric-badge ${
              drawdowns.is_recovered ? 'badge-success' : 'badge-warning'
            }`}
          >
            {drawdowns.is_recovered ? 'RECOVERED' : 'IN DRAWDOWN'}
          </span>
        </div>
        <div className="metric-value-large negative">{maxDdNum.toFixed(2)}%</div>
        <div className="metric-subtext">
          <span>
            {drawdowns.max_drawdown_peak_date} → {drawdowns.max_drawdown_trough_date}
          </span>
          <span>Current: {currentDdNum.toFixed(2)}%</span>
        </div>
      </div>

      {/* 6. Period Extremes */}
      <div className="metric-card">
        <div className="metric-header">
          <span className="metric-label">PERIOD EXTREMES</span>
          <span className="metric-badge">RAW CLOSE</span>
        </div>
        <div className="extremes-row">
          <div className="extreme-item">
            <span className="extreme-label">HIGH:</span>
            <span className="extreme-val">${extremes.period_high}</span>
            <span className="extreme-dist negative">
              {extremes.distance_from_high}%
            </span>
          </div>
          <div className="extreme-item">
            <span className="extreme-label">LOW:</span>
            <span className="extreme-val">${extremes.period_low}</span>
            <span className="extreme-dist positive">
              +{extremes.distance_from_low}%
            </span>
          </div>
        </div>
        <div className="metric-subtext">
          <span>High: {extremes.period_high_date}</span>
          <span>Low: {extremes.period_low_date}</span>
        </div>
      </div>

      {/* 7. Benchmark Comparison (if available) */}
      {benchmark_comparison && (
        <div className="metric-card metric-card-wide">
          <div className="metric-header">
            <span className="metric-label">
              BENCHMARK: {benchmark_comparison.benchmark_name} ({benchmark_comparison.benchmark_id})
            </span>
            <span className="metric-badge">BASE: {benchmark_comparison.common_base_date}</span>
          </div>
          <div className="benchmark-comparison-stats">
            <div className="bmk-stat">
              <span className="bmk-label">SECURITY RETURN</span>
              <span className="bmk-val">
                {(parseFloat(benchmark_comparison.security_return) * 100).toFixed(2)}%
              </span>
            </div>
            <div className="bmk-stat">
              <span className="bmk-label">S&amp;P 500 RETURN</span>
              <span className="bmk-val">
                {(parseFloat(benchmark_comparison.benchmark_return) * 100).toFixed(2)}%
              </span>
            </div>
            <div className="bmk-stat">
              <span className="bmk-label">EXCESS RETURN</span>
              <span
                className={`bmk-val ${
                  parseFloat(benchmark_comparison.excess_return) >= 0
                    ? 'positive'
                    : 'negative'
                }`}
              >
                {parseFloat(benchmark_comparison.excess_return) >= 0 ? '+' : ''}
                {(parseFloat(benchmark_comparison.excess_return) * 100).toFixed(2)}%
              </span>
            </div>
            <div className="bmk-stat">
              <span className="bmk-label">CORRELATION (ρ)</span>
              <span className="bmk-val">{benchmark_comparison.correlation}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
