import React, { useState } from 'react';
import type { MarketMoverItem } from '../../types/overview';
import { MoversTable } from './MoversTable';

interface MarketMoversGridProps {
  gainers: MarketMoverItem[];
  losers: MarketMoverItem[];
  active: MarketMoverItem[];
  onSelectTicker: (ticker: string) => void;
}

type MoverTab = 'ALL' | 'GAINERS' | 'LOSERS' | 'ACTIVE';

export const MarketMoversGrid: React.FC<MarketMoversGridProps> = ({
  gainers,
  losers,
  active,
  onSelectTicker,
}) => {
  const [activeTab, setActiveTab] = useState<MoverTab>('ALL');

  return (
    <section className="market-movers-section">
      <div className="section-header">
        <div className="section-title-group">
          <span className="section-bullet">◈</span>
          <h2 className="section-heading">SESSION MARKET MOVERS</h2>
        </div>

        <div className="mover-tabs">
          <button
            type="button"
            className={`mover-tab-button ${activeTab === 'ALL' ? 'active' : ''}`}
            onClick={() => setActiveTab('ALL')}
          >
            ALL CATEGORIES
          </button>
          <button
            type="button"
            className={`mover-tab-button ${activeTab === 'GAINERS' ? 'active' : ''}`}
            onClick={() => setActiveTab('GAINERS')}
          >
            ▲ GAINERS ({gainers.length})
          </button>
          <button
            type="button"
            className={`mover-tab-button ${activeTab === 'LOSERS' ? 'active' : ''}`}
            onClick={() => setActiveTab('LOSERS')}
          >
            ▼ LOSERS ({losers.length})
          </button>
          <button
            type="button"
            className={`mover-tab-button ${activeTab === 'ACTIVE' ? 'active' : ''}`}
            onClick={() => setActiveTab('ACTIVE')}
          >
            ◆ MOST ACTIVE ({active.length})
          </button>
        </div>
      </div>

      <div className={`movers-grid-layout ${activeTab !== 'ALL' ? 'single-col' : ''}`}>
        {(activeTab === 'ALL' || activeTab === 'GAINERS') && (
          <MoversTable
            title="TOP SESSION GAINERS"
            category="GAINERS"
            movers={gainers}
            onSelectTicker={onSelectTicker}
          />
        )}

        {(activeTab === 'ALL' || activeTab === 'LOSERS') && (
          <MoversTable
            title="TOP SESSION LOSERS"
            category="LOSERS"
            movers={losers}
            onSelectTicker={onSelectTicker}
          />
        )}

        {(activeTab === 'ALL' || activeTab === 'ACTIVE') && (
          <MoversTable
            title="SESSION VOLUME LEADERS"
            category="ACTIVE"
            movers={active}
            onSelectTicker={onSelectTicker}
          />
        )}
      </div>
    </section>
  );
};
