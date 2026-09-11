import React, { useCallback, useEffect, useState } from 'react';
import { fetchHistoricalAnalysis } from '../../api/historical';
import type {
  HistoricalAnalysisResponse,
  HistoricalTimeHorizon,
} from '../../types/historical';
import { ErrorMessage } from '../ui/ErrorMessage';
import { HistoricalChart } from './HistoricalChart';
import { HistoricalMetricsGrid } from './HistoricalMetricsGrid';
import { HistoricalSessionTable } from './HistoricalSessionTable';
import { HorizonSelector } from './HorizonSelector';

interface HistoricalAnalysisViewProps {
  initialTicker?: string;
  onSelectTicker?: (ticker: string) => void;
}

const QUICK_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'SPY', 'GOOGL', 'AMZN', 'TSLA'];

export const HistoricalAnalysisView: React.FC<HistoricalAnalysisViewProps> = ({
  initialTicker = 'AAPL',
  onSelectTicker,
}) => {
  const [ticker, setTicker] = useState<string>(initialTicker);
  const [inputTicker, setInputTicker] = useState<string>(initialTicker);
  const [horizon, setHorizon] = useState<HistoricalTimeHorizon>('1Y');
  const [customStart, setCustomStart] = useState<string | undefined>(undefined);
  const [customEnd, setCustomEnd] = useState<string | undefined>(undefined);
  const [includeBenchmark, setIncludeBenchmark] = useState<boolean>(true);
  const [analysis, setAnalysis] = useState<HistoricalAnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const loadAnalysis = useCallback(
    async (
      sym: string,
      hor: HistoricalTimeHorizon,
      cStart?: string,
      cEnd?: string,
      includeBmk: boolean = true,
      forceRefresh: boolean = false
    ) => {
      setIsLoading(true);
      setError(null);

      try {
        const res = await fetchHistoricalAnalysis(sym, hor, {
          startDate: cStart,
          endDate: cEnd,
          includeBenchmark: includeBmk,
          forceRefresh,
        });
        setAnalysis(res);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setAnalysis(null);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    loadAnalysis(ticker, horizon, customStart, customEnd, includeBenchmark);
  }, [ticker, horizon, customStart, customEnd, includeBenchmark, loadAnalysis]);

  const handleSelectHorizon = (
    newHorizon: HistoricalTimeHorizon,
    newStart?: string,
    newEnd?: string
  ) => {
    setHorizon(newHorizon);
    setCustomStart(newStart);
    setCustomEnd(newEnd);
  };

  const handleTickerSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = inputTicker.trim().toUpperCase();
    if (clean) {
      setTicker(clean);
      if (onSelectTicker) {
        onSelectTicker(clean);
      }
    }
  };

  const handleQuickTicker = (sym: string) => {
    setInputTicker(sym);
    setTicker(sym);
    if (onSelectTicker) {
      onSelectTicker(sym);
    }
  };

  const handleRefresh = () => {
    loadAnalysis(ticker, horizon, customStart, customEnd, includeBenchmark, true);
  };

  return (
    <div className="historical-analysis-view">
      {/* Top Controls Bar */}
      <div className="historical-top-bar">
        <form className="historical-ticker-form" onSubmit={handleTickerSubmit}>
          <span className="ticker-search-icon">☵</span>
          <input
            type="text"
            className="historical-ticker-input"
            value={inputTicker}
            onChange={(e) => setInputTicker(e.target.value.toUpperCase())}
            placeholder="ENTER TICKER..."
          />
          <button type="submit" className="historical-load-btn" disabled={isLoading}>
            ANALYZE
          </button>
        </form>

        <div className="quick-tickers-list">
          <span className="quick-label">QUICK:</span>
          {QUICK_TICKERS.map((sym) => (
            <button
              key={sym}
              type="button"
              className={`quick-ticker-chip ${ticker === sym ? 'active' : ''}`}
              onClick={() => handleQuickTicker(sym)}
              disabled={isLoading}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>

      {/* Horizon & Benchmark Controls */}
      <HorizonSelector
        currentHorizon={horizon}
        onSelectHorizon={handleSelectHorizon}
        includeBenchmark={includeBenchmark}
        onToggleBenchmark={setIncludeBenchmark}
        isLoading={isLoading}
        onRefresh={handleRefresh}
      />

      {/* Error state */}
      {error && (
        <ErrorMessage
          error={error}
          onRetry={() =>
            loadAnalysis(ticker, horizon, customStart, customEnd, includeBenchmark, true)
          }
        />
      )}

      {/* Loading state */}
      {isLoading && !analysis && (
        <div className="loading-state">
          COMPUTING HISTORICAL ANALYTICS &amp; BENCHMARKS FOR {ticker}...
        </div>
      )}

      {/* Analysis Content */}
      {analysis && (
        <div className="historical-content">
          {/* Header Summary */}
          <div className="analysis-summary-strip">
            <div className="summary-strip-left">
              <span className="ticker-badge">{analysis.ticker}</span>
              <span className="horizon-badge">{analysis.horizon}</span>
              <span className="date-range">
                {analysis.start_date} → {analysis.end_date}
              </span>
            </div>
            <div className="summary-strip-right">
              <span className="stat-pill">
                <strong>{analysis.trading_days}</strong> TRADING SESSIONS
              </span>
              <span className="stat-pill">
                <strong>{analysis.calendar_days}</strong> CALENDAR DAYS
              </span>
              <span className="provider-tag">PROVIDER: {analysis.provider}</span>
            </div>
          </div>

          {/* Metrics Grid */}
          <HistoricalMetricsGrid analysis={analysis} />

          {/* Interactive Chart */}
          <HistoricalChart series={analysis.series} ticker={analysis.ticker} />

          {/* Audit Trail Session Table */}
          <HistoricalSessionTable
            series={analysis.series}
            ticker={analysis.ticker}
          />

          {/* Institutional Methodology Footnote */}
          <div className="methodology-callout">
            <div className="callout-title">
              <span className="callout-icon">ℹ</span>
              <span>INSTITUTIONAL QUANTITATIVE METHODOLOGY &amp; POLICIES</span>
            </div>
            <ul className="callout-list">
              <li>
                <strong>Price Series Policy:</strong> Technical indicators (SMA20, SMA50, SMA200, EMA20) and Period Extremes are calculated strictly on nominal raw Close prices. Return series, CAGR, win rate, and drawdowns are calculated on provider-adjusted Close (<code>adj_close</code>) to preserve split/dividend continuity.
              </li>
              <li>
                <strong>Adjusted Price Return:</strong> Formally named <em>Adjusted Price Return</em> (not "Total Return") as provider <code>adj_close</code> is a proxy for modeled split and cash dividend effects rather than an investor accounting total-return series.
              </li>
              <li>
                <strong>Calendar-Time CAGR:</strong> Compounding is evaluated over actual elapsed calendar days (<code>(P_end / P_start) ** (365.2425 / calendar_days) - 1</code>) for horizons ≥ 365 calendar days.
              </li>
              <li>
                <strong>Realized Volatility:</strong> Daily sample standard deviation is calculated with Bessel correction (N-1) requiring at least 2 daily returns (3 price observations), annualized using <code>√252</code>.
              </li>
              <li>
                <strong>Benchmark Inner Alignment:</strong> Security and S&amp;P 500 (^GSPC) series are inner-aligned on matched trading dates, rebased to 100.0 at the common base date.
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};
