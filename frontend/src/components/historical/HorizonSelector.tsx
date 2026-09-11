import React, { useState } from 'react';
import type { HistoricalTimeHorizon } from '../../types/historical';

interface HorizonSelectorProps {
  currentHorizon: HistoricalTimeHorizon;
  onSelectHorizon: (
    horizon: HistoricalTimeHorizon,
    customStart?: string,
    customEnd?: string
  ) => void;
  includeBenchmark: boolean;
  onToggleBenchmark: (include: boolean) => void;
  isLoading: boolean;
  onRefresh: () => void;
}

const HORIZONS: { label: string; value: HistoricalTimeHorizon }[] = [
  { label: '1M', value: '1M' },
  { label: '3M', value: '3M' },
  { label: '6M', value: '6M' },
  { label: 'YTD', value: 'YTD' },
  { label: '1Y', value: '1Y' },
  { label: '3Y', value: '3Y' },
  { label: '5Y', value: '5Y' },
  { label: 'MAX', value: 'MAX' },
  { label: 'CUSTOM', value: 'CUSTOM' },
];

export const HorizonSelector: React.FC<HorizonSelectorProps> = ({
  currentHorizon,
  onSelectHorizon,
  includeBenchmark,
  onToggleBenchmark,
  isLoading,
  onRefresh,
}) => {
  const [customStart, setCustomStart] = useState<string>('');
  const [customEnd, setCustomEnd] = useState<string>('');
  const [showCustomInputs, setShowCustomInputs] = useState<boolean>(
    currentHorizon === 'CUSTOM'
  );

  const handleHorizonClick = (horizon: HistoricalTimeHorizon) => {
    if (horizon === 'CUSTOM') {
      setShowCustomInputs(true);
    } else {
      setShowCustomInputs(false);
      onSelectHorizon(horizon);
    }
  };

  const handleApplyCustom = (e: React.FormEvent) => {
    e.preventDefault();
    if (customStart && customEnd) {
      onSelectHorizon('CUSTOM', customStart, customEnd);
    }
  };

  return (
    <div className="historical-horizon-bar">
      <div className="horizon-button-group">
        <span className="horizon-group-label">HORIZON:</span>
        {HORIZONS.map((h) => (
          <button
            key={h.value}
            type="button"
            className={`horizon-btn ${currentHorizon === h.value ? 'active' : ''}`}
            onClick={() => handleHorizonClick(h.value)}
            disabled={isLoading}
          >
            {h.label}
          </button>
        ))}
      </div>

      <div className="horizon-controls-right">
        <label className="benchmark-toggle-label">
          <input
            type="checkbox"
            checked={includeBenchmark}
            onChange={(e) => onToggleBenchmark(e.target.checked)}
            disabled={isLoading}
          />
          <span>COMPARE S&amp;P 500</span>
        </label>

        <button
          type="button"
          className="refresh-btn"
          onClick={onRefresh}
          disabled={isLoading}
          title="Force refresh data from provider"
        >
          {isLoading ? 'SYNCING...' : '↻ REFRESH'}
        </button>
      </div>

      {showCustomInputs && (
        <form className="custom-date-form" onSubmit={handleApplyCustom}>
          <div className="date-input-group">
            <label htmlFor="custom-start-date">FROM:</label>
            <input
              id="custom-start-date"
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              required
            />
          </div>
          <div className="date-input-group">
            <label htmlFor="custom-end-date">TO:</label>
            <input
              id="custom-end-date"
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="custom-apply-btn" disabled={isLoading}>
            APPLY DATES
          </button>
        </form>
      )}
    </div>
  );
};
