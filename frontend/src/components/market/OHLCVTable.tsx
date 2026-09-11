import React from 'react';
import type { OHLCVResponse } from '../../types/market';
import { formatDate, formatPrice, formatVolume } from '../../utils/formatters';

interface OHLCVTableProps {
  series: OHLCVResponse;
}

export const OHLCVTable: React.FC<OHLCVTableProps> = ({ series }) => {
  // Show most recent bars first for standard financial terminal view
  const reversedBars = [...series.bars].reverse();

  return (
    <div className="table-card">
      <div className="table-header-row">
        <div>
          <h3 className="table-title">HISTORICAL DAILY OHLCV</h3>
          <span className="table-subtitle">
            {series.ticker} • {series.bars.length} TRADING SESSIONS • INTERVAL: {series.interval.toUpperCase()}
          </span>
        </div>
        <div className="series-badge">
          {series.is_adjusted ? 'ADJ CLOSE AVAILABLE' : 'RAW ONLY'}
        </div>
      </div>

      <div className="table-wrapper">
        <table className="terminal-table">
          <thead>
            <tr>
              <th>DATE</th>
              <th className="num-col">OPEN</th>
              <th className="num-col">HIGH</th>
              <th className="num-col">LOW</th>
              <th className="num-col">CLOSE (RAW)</th>
              <th className="num-col">VOLUME</th>
              <th className="num-col">ADJ CLOSE*</th>
            </tr>
          </thead>
          <tbody>
            {reversedBars.map((bar) => {
              const isOpenClosePositive = parseFloat(bar.close) >= parseFloat(bar.open);
              return (
                <tr key={bar.timestamp}>
                  <td className="date-cell">{formatDate(bar.timestamp)}</td>
                  <td className="num-col">{formatPrice(bar.open)}</td>
                  <td className="num-col">{formatPrice(bar.high)}</td>
                  <td className="num-col">{formatPrice(bar.low)}</td>
                  <td className={`num-col close-cell ${isOpenClosePositive ? 'up' : 'down'}`}>
                    {formatPrice(bar.close)}
                  </td>
                  <td className="num-col">{formatVolume(bar.volume)}</td>
                  <td className="num-col adj-cell">{formatPrice(bar.adj_close)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="table-disclaimers">
        <p>
          <strong>Financial Semantics & Invariants:</strong> Raw OHLC prices (Open, High, Low, Close) reflect actual historical transaction prices and remain strictly unadjusted.
        </p>
        <p>
          <strong>* Adjusted Close Disclaimer:</strong> <code>adj_close</code> is a provider-specific adjusted historical close (from Yahoo Finance) reflecting corporate actions (splits, dividend distributions). It must <em>not</em> automatically be interpreted as an exact investor total-return series, as it does not account for taxes, trade execution friction, or reinvestment cash timings.
        </p>
        <p>
          <strong>Volume:</strong> Whole-share transaction count reported by exchanges.
        </p>
      </div>
    </div>
  );
};
