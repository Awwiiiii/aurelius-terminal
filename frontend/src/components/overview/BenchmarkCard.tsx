import React from 'react';
import type { BenchmarkSnapshot } from '../../types/overview';
import { formatChange, formatPrice } from '../../utils/formatters';

interface BenchmarkCardProps {
  benchmark: BenchmarkSnapshot;
  onSelect?: (benchmarkId: string) => void;
}

export const BenchmarkCard: React.FC<BenchmarkCardProps> = ({
  benchmark,
  onSelect,
}) => {
  const { is_currency_priced, benchmark_id, name, category, price, change, change_percent } =
    benchmark;

  const changeInfo = formatChange(change, change_percent);

  // Format price: for VIX, quote strictly in points without currency sign!
  const formattedPrice = is_currency_priced
    ? formatPrice(price, benchmark.currency)
    : `${parseFloat(price).toFixed(2)} pts`;

  const getCategoryDisplay = (cat: string) => {
    switch (cat) {
      case 'LARGE_CAP_CORE':
        return 'LARGE CAP';
      case 'MEGA_CAP_VALUE':
        return 'MEGA CAP VALUE';
      case 'TECH_GROWTH':
        return 'TECH & GROWTH';
      case 'SMALL_CAP':
        return 'SMALL CAP';
      case 'VOLATILITY':
        return 'VOLATILITY INDEX';
      default:
        return cat;
    }
  };

  return (
    <div
      className={`benchmark-card ${onSelect ? 'clickable' : ''}`}
      onClick={() => onSelect && onSelect(benchmark_id)}
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
    >
      <div className="benchmark-card-header">
        <div className="benchmark-title-group">
          <span className="benchmark-id">{benchmark_id}</span>
          <span className="benchmark-category-badge">
            {getCategoryDisplay(category)}
          </span>
        </div>
        <span className="benchmark-name" title={name}>
          {name}
        </span>
      </div>

      <div className="benchmark-price-section">
        <div className="benchmark-price-value">{formattedPrice}</div>
        <div
          className={`benchmark-change-value ${
            changeInfo.isPositive
              ? 'positive'
              : changeInfo.isNegative
              ? 'negative'
              : 'neutral'
          }`}
        >
          {changeInfo.text}
        </div>
      </div>

      <div className="benchmark-card-footer">
        <div className="benchmark-metric">
          <span className="metric-label">PREV CLOSE</span>
          <span className="metric-value">
            {benchmark.previous_close
              ? is_currency_priced
                ? formatPrice(benchmark.previous_close)
                : `${parseFloat(benchmark.previous_close).toFixed(2)}`
              : '—'}
          </span>
        </div>
        <div className="benchmark-metric">
          <span className="metric-label">RANGE</span>
          <span className="metric-value">
            {benchmark.day_low && benchmark.day_high
              ? `${parseFloat(benchmark.day_low).toFixed(1)} - ${parseFloat(
                  benchmark.day_high
                ).toFixed(1)}`
              : '—'}
          </span>
        </div>
      </div>

      {!is_currency_priced && (
        <div className="vix-footnote">
          * Quoted in 30-day forward annualized implied volatility points.
        </div>
      )}
    </div>
  );
};
