import React from 'react';
import type { MarketMoverItem } from '../../types/overview';
import {
  formatChange,
  formatMarketCap,
  formatPrice,
  formatVolume,
} from '../../utils/formatters';

interface MoversTableProps {
  title: string;
  category: 'GAINERS' | 'LOSERS' | 'ACTIVE';
  movers: MarketMoverItem[];
  onSelectTicker: (ticker: string) => void;
}

export const MoversTable: React.FC<MoversTableProps> = ({
  title,
  category,
  movers,
  onSelectTicker,
}) => {
  const getHeaderIcon = (cat: string) => {
    switch (cat) {
      case 'GAINERS':
        return '▲';
      case 'LOSERS':
        return '▼';
      case 'ACTIVE':
      default:
        return '◆';
    }
  };

  const getHeaderClass = (cat: string) => {
    switch (cat) {
      case 'GAINERS':
        return 'movers-gainers';
      case 'LOSERS':
        return 'movers-losers';
      case 'ACTIVE':
      default:
        return 'movers-active';
    }
  };

  return (
    <div className={`movers-table-container ${getHeaderClass(category)}`}>
      <div className="movers-table-header">
        <div className="movers-title-wrap">
          <span className="movers-icon">{getHeaderIcon(category)}</span>
          <h3 className="movers-title">{title}</h3>
        </div>
        <span className="movers-count-badge">{movers.length} SECURITIES</span>
      </div>

      <div className="movers-table-scroll">
        <table className="terminal-table movers-table">
          <thead>
            <tr>
              <th className="th-rank">#</th>
              <th className="th-ticker">TICKER</th>
              <th className="th-name">SECURITY</th>
              <th className="th-price text-right">PRICE</th>
              <th className="th-change text-right">CHANGE</th>
              <th className="th-volume text-right">VOLUME</th>
              <th className="th-mcap text-right">MKT CAP</th>
              <th className="th-exch text-center">EXCH</th>
            </tr>
          </thead>
          <tbody>
            {movers.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-table-cell">
                  No active securities recorded in this mover screen.
                </td>
              </tr>
            ) : (
              movers.map((item, index) => {
                const changeInfo = formatChange(
                  item.change,
                  item.change_percent
                );
                return (
                  <tr
                    key={`${item.ticker}-${category}-${index}`}
                    className="mover-row"
                  >
                    <td className="td-rank">{index + 1}</td>
                    <td className="td-ticker">
                      <button
                        type="button"
                        className="ticker-jump-button"
                        onClick={() => onSelectTicker(item.ticker)}
                        title={`Analyze ${item.ticker} in Research Terminal`}
                      >
                        {item.ticker}
                      </button>
                    </td>
                    <td className="td-name" title={item.name}>
                      <span className="truncate-text">{item.name}</span>
                    </td>
                    <td className="td-price text-right font-mono">
                      {formatPrice(item.price)}
                    </td>
                    <td
                      className={`td-change text-right font-mono ${
                        changeInfo.isPositive
                          ? 'positive'
                          : changeInfo.isNegative
                          ? 'negative'
                          : 'neutral'
                      }`}
                    >
                      {changeInfo.text}
                    </td>
                    <td className="td-volume text-right font-mono">
                      {item.volume !== null ? formatVolume(item.volume) : '—'}
                    </td>
                    <td className="td-mcap text-right font-mono">
                      {item.market_cap !== null
                        ? formatMarketCap(item.market_cap)
                        : '—'}
                    </td>
                    <td className="td-exch text-center">
                      <span className="exchange-pill">
                        {item.exchange || 'US'}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
