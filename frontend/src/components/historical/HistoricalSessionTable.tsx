import React, { useState } from 'react';
import type { HistoricalBarPointResponse } from '../../types/historical';

interface HistoricalSessionTableProps {
  series: HistoricalBarPointResponse[];
  ticker: string;
}

export const HistoricalSessionTable: React.FC<HistoricalSessionTableProps> = ({
  series,
  ticker,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [page, setPage] = useState<number>(0);
  const pageSize = 15;

  // Show newest bars first
  const reversed = [...series].reverse();
  const totalPages = Math.ceil(reversed.length / pageSize);
  const displayedBars = reversed.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <div className="historical-table-container">
      <div
        className="historical-table-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="table-title">
          <span className="expand-indicator">{isExpanded ? '▼' : '▶'}</span>
          <span>
            HISTORICAL TRADING SESSIONS ({series.length} OBSERVATIONS) — {ticker}
          </span>
        </div>
        <span className="table-hint">
          {isExpanded ? 'CLICK TO COLLAPSE' : 'CLICK TO EXPAND AUDIT TRAIL'}
        </span>
      </div>

      {isExpanded && (
        <div className="table-body-wrapper">
          <div className="table-responsive">
            <table className="historical-audit-table">
              <thead>
                <tr>
                  <th>DATE</th>
                  <th>OPEN</th>
                  <th>HIGH</th>
                  <th>LOW</th>
                  <th>CLOSE</th>
                  <th>ADJ CLOSE*</th>
                  <th>VOLUME</th>
                  <th>DAILY RET</th>
                  <th>DRAWDOWN</th>
                  <th>SMA 20</th>
                  <th>EMA 20</th>
                </tr>
              </thead>
              <tbody>
                {displayedBars.map((bar) => {
                  const retNum = bar.daily_return
                    ? parseFloat(bar.daily_return) * 100
                    : null;
                  const ddNum = parseFloat(bar.drawdown) * 100;

                  return (
                    <tr key={bar.date}>
                      <td className="date-cell">{bar.date}</td>
                      <td>${bar.open}</td>
                      <td>${bar.high}</td>
                      <td>${bar.low}</td>
                      <td>${bar.close}</td>
                      <td className="adj-cell">${bar.adj_close}</td>
                      <td>{bar.volume.toLocaleString()}</td>
                      <td
                        className={
                          retNum === null
                            ? ''
                            : retNum >= 0
                            ? 'positive'
                            : 'negative'
                        }
                      >
                        {retNum !== null
                          ? `${retNum >= 0 ? '+' : ''}${retNum.toFixed(2)}%`
                          : '—'}
                      </td>
                      <td className="negative">{ddNum.toFixed(2)}%</td>
                      <td>{bar.sma_20 ? `$${bar.sma_20}` : '—'}</td>
                      <td>{bar.ema_20 ? `$${bar.ema_20}` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="table-pagination">
              <button
                type="button"
                className="pagination-btn"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                ◀ PREV
              </button>
              <span className="pagination-info">
                PAGE {page + 1} OF {totalPages}
              </span>
              <button
                type="button"
                className="pagination-btn"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              >
                NEXT ▶
              </button>
            </div>
          )}

          <div className="table-footnote">
            * <em>ADJ CLOSE represents provider-specific split/dividend adjustment proxy. Nominal indicators (SMA, EMA, Extremes) are calculated on raw Close.</em>
          </div>
        </div>
      )}
    </div>
  );
};
