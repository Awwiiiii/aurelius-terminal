import React from 'react';
import type { QuoteResponse } from '../../types/market';
import { formatChange, formatPrice, formatVolume } from '../../utils/formatters';

interface QuoteCardProps {
  quote: QuoteResponse;
}

export const QuoteCard: React.FC<QuoteCardProps> = ({ quote }) => {
  const changeInfo = formatChange(quote.change, quote.change_percent);

  return (
    <div className="quote-card">
      <div className="quote-top-row">
        <div className="quote-identity">
          <span className="quote-ticker">{quote.ticker}</span>
          <span className="quote-currency">{quote.currency}</span>
          <span className="market-state-badge">{quote.market_state}</span>
        </div>
        <div className="quote-provider-meta">
          <span className="provider-name">{quote.provider}</span>
          {quote.is_delayed && (
            <span className="delay-badge" title="Data subject to provider delay (typically ~15 min during market hours)">
              DELAYED (~15M)
            </span>
          )}
        </div>
      </div>

      <div className="quote-price-row">
        <div className="quote-main-price">
          <span className="price-currency-symbol">$</span>
          <span className="price-value">{formatPrice(quote.price)}</span>
        </div>
        <div
          className={`quote-change ${
            changeInfo.isPositive ? 'positive' : changeInfo.isNegative ? 'negative' : 'neutral'
          }`}
        >
          {changeInfo.text}
        </div>
      </div>

      <div className="quote-stats-grid">
        <div className="stat-item">
          <span className="stat-label">DAY RANGE</span>
          <span className="stat-val">
            {formatPrice(quote.low)} – {formatPrice(quote.high)}
          </span>
        </div>

        <div className="stat-item">
          <span className="stat-label">OPEN</span>
          <span className="stat-val">{formatPrice(quote.open)}</span>
        </div>

        <div className="stat-item">
          <span className="stat-label">PREV CLOSE</span>
          <span className="stat-val">{formatPrice(quote.previous_close)}</span>
        </div>

        <div className="stat-item">
          <span className="stat-label">VOLUME (SHARES)*</span>
          <span className="stat-val">{formatVolume(quote.volume)}</span>
        </div>
      </div>

      <div className="card-footnote">
        * Note: Market volume is reported in whole shares per exchange standards. Quotes are subject to provider limitations.
      </div>
    </div>
  );
};
