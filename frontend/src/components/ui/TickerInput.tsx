import React, { useState } from 'react';

interface TickerInputProps {
  currentTicker: string;
  onSelectTicker: (ticker: string) => void;
  isLoading: boolean;
}

const QUICK_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'SPY', 'QQQ'];

export const TickerInput: React.FC<TickerInputProps> = ({
  currentTicker,
  onSelectTicker,
  isLoading,
}) => {
  const [inputVal, setInputVal] = useState(currentTicker);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = inputVal.trim().toUpperCase();
    if (cleaned) {
      onSelectTicker(cleaned);
    }
  };

  return (
    <div className="ticker-bar-container">
      <form onSubmit={handleSubmit} className="ticker-form">
        <div className="input-prefix">TICKER:</div>
        <input
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value.toUpperCase())}
          placeholder="e.g. AAPL, MSFT"
          className="ticker-input"
          disabled={isLoading}
          maxLength={12}
        />
        <button type="submit" className="ticker-submit-btn" disabled={isLoading || !inputVal.trim()}>
          {isLoading ? 'FETCHING...' : 'LOAD SECURITY'}
        </button>
      </form>

      <div className="quick-tickers">
        <span className="quick-label">QUICK:</span>
        {QUICK_TICKERS.map((t) => (
          <button
            key={t}
            type="button"
            className={`quick-pill ${currentTicker === t ? 'active' : ''}`}
            onClick={() => {
              setInputVal(t);
              onSelectTicker(t);
            }}
            disabled={isLoading}
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  );
};
