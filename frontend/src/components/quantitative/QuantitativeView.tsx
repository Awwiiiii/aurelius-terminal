import React, { useCallback, useEffect, useState } from 'react';
import {
  fetchAssetComparison,
  fetchReturnDistribution,
  fetchRollingSeries,
} from '../../api/quantitative';
import type { HistoricalTimeHorizon } from '../../types/historical';
import type {
  MultiAssetCorrelationMatrixResponse,
  QuantitativeMetricType,
  ReturnCalculationType,
  ReturnDistributionSummaryResponse,
  RollingQuantitativeSeriesResponse,
} from '../../types/quantitative';
import { ErrorMessage } from '../ui/ErrorMessage';
import { CorrelationMatrixHeatmap } from './CorrelationMatrixHeatmap';
import { ReturnDistributionInspector } from './ReturnDistributionInspector';
import { RollingCorrelationChart } from './RollingCorrelationChart';

interface QuantitativeViewProps {
  initialTicker?: string;
  onSelectTicker?: (ticker: string) => void;
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
];

export const QuantitativeView: React.FC<QuantitativeViewProps> = ({
  initialTicker = 'AAPL',
  onSelectTicker,
}) => {
  const [activeTab, setActiveTab] = useState<
    'DISTRIBUTION' | 'CORRELATION' | 'ROLLING'
  >('DISTRIBUTION');
  const [ticker, setTicker] = useState<string>(initialTicker);
  const [tickerInput, setTickerInput] = useState<string>(initialTicker);
  const [horizon, setHorizon] = useState<HistoricalTimeHorizon>('1Y');
  const [returnType, setReturnType] = useState<ReturnCalculationType>('SIMPLE');

  // Distribution tab state
  const [distData, setDistData] =
    useState<ReturnDistributionSummaryResponse | null>(null);
  const [isDistLoading, setIsDistLoading] = useState<boolean>(false);
  const [distError, setDistError] = useState<Error | null>(null);

  // Correlation matrix state
  const [matrixTickers, setMatrixTickers] = useState<string[]>([
    initialTicker,
    'MSFT',
    'NVDA',
    'GOOGL',
  ]);
  const [matrixData, setMatrixData] =
    useState<MultiAssetCorrelationMatrixResponse | null>(null);
  const [isMatrixLoading, setIsMatrixLoading] = useState<boolean>(false);
  const [matrixError, setMatrixError] = useState<Error | null>(null);

  // Rolling metrics state
  const [rollingMetric, setRollingMetric] =
    useState<QuantitativeMetricType>('VOLATILITY');
  const [rollingWindow, setRollingWindow] = useState<number>(20);
  const [rollingTickerB, setRollingTickerB] = useState<string>('SPY');
  const [rollingData, setRollingData] =
    useState<RollingQuantitativeSeriesResponse | null>(null);
  const [isRollingLoading, setIsRollingLoading] = useState<boolean>(false);
  const [rollingError, setRollingError] = useState<Error | null>(null);

  // Load Distribution Data
  const loadDistribution = useCallback(
    async (targetTicker: string, h: HistoricalTimeHorizon, rt: ReturnCalculationType, force = false) => {
      setIsDistLoading(true);
      setDistError(null);
      try {
        const res = await fetchReturnDistribution(targetTicker, h, rt, {
          forceRefresh: force,
        });
        setDistData(res);
      } catch (err) {
        setDistError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsDistLoading(false);
      }
    },
    []
  );

  // Load Multi-Asset Correlation Data
  const loadCorrelation = useCallback(
    async (tickers: string[], h: HistoricalTimeHorizon, force = false) => {
      setIsMatrixLoading(true);
      setMatrixError(null);
      try {
        const res = await fetchAssetComparison(tickers, h, {
          forceRefresh: force,
        });
        setMatrixData(res);
      } catch (err) {
        setMatrixError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsMatrixLoading(false);
      }
    },
    []
  );

  // Load Rolling Series Data
  const loadRolling = useCallback(
    async (
      targetTicker: string,
      m: QuantitativeMetricType,
      w: number,
      secTicker: string,
      h: HistoricalTimeHorizon,
      force = false
    ) => {
      setIsRollingLoading(true);
      setRollingError(null);
      try {
        const res = await fetchRollingSeries(
          targetTicker,
          m,
          w,
          secTicker,
          h,
          { forceRefresh: force }
        );
        setRollingData(res);
      } catch (err) {
        setRollingError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsRollingLoading(false);
      }
    },
    []
  );

  // Initial and trigger effects
  useEffect(() => {
    if (activeTab === 'DISTRIBUTION') {
      loadDistribution(ticker, horizon, returnType);
    } else if (activeTab === 'CORRELATION') {
      loadCorrelation(matrixTickers, horizon);
    } else if (activeTab === 'ROLLING') {
      loadRolling(ticker, rollingMetric, rollingWindow, rollingTickerB, horizon);
    }
  }, [
    activeTab,
    ticker,
    horizon,
    returnType,
    matrixTickers,
    rollingMetric,
    rollingWindow,
    rollingTickerB,
    loadDistribution,
    loadCorrelation,
    loadRolling,
  ]);

  const handleTickerSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = tickerInput.trim().toUpperCase();
    if (clean) {
      setTicker(clean);
      if (onSelectTicker) onSelectTicker(clean);
    }
  };

  return (
    <div className="quant-workspace-container">
      {/* Top Workspace Header & Navigation Tabs */}
      <div className="quant-top-bar">
        <div className="quant-tab-nav">
          <button
            type="button"
            className={`quant-tab-btn ${
              activeTab === 'DISTRIBUTION' ? 'active' : ''
            }`}
            onClick={() => setActiveTab('DISTRIBUTION')}
          >
            <span className="quant-tab-icon">⨀</span>
            <span>RETURN DISTRIBUTION</span>
          </button>
          <button
            type="button"
            className={`quant-tab-btn ${
              activeTab === 'CORRELATION' ? 'active' : ''
            }`}
            onClick={() => setActiveTab('CORRELATION')}
          >
            <span className="quant-tab-icon">⊞</span>
            <span>MULTI-ASSET CORRELATION</span>
          </button>
          <button
            type="button"
            className={`quant-tab-btn ${
              activeTab === 'ROLLING' ? 'active' : ''
            }`}
            onClick={() => setActiveTab('ROLLING')}
          >
            <span className="quant-tab-icon">∿</span>
            <span>ROLLING METRICS</span>
          </button>
        </div>

        {/* Global Toolbar Filters */}
        <div className="quant-global-filters">
          {activeTab !== 'CORRELATION' && (
            <form onSubmit={handleTickerSubmit} className="quant-ticker-search">
              <label htmlFor="quant-single-ticker-input" className="visually-hidden">
                Primary Security Ticker
              </label>
              <input
                id="quant-single-ticker-input"
                type="text"
                value={tickerInput}
                onChange={(e) => setTickerInput(e.target.value)}
                placeholder="TICKER"
                className="quant-ticker-input-field"
              />
              <button type="submit" className="quant-search-btn">
                GO
              </button>
            </form>
          )}

          {/* Horizon Selector */}
          <div className="quant-horizon-selector">
            {HORIZONS.map((h) => (
              <button
                key={h.value}
                type="button"
                className={`quant-horizon-pill ${
                  horizon === h.value ? 'active' : ''
                }`}
                onClick={() => setHorizon(h.value)}
              >
                {h.label}
              </button>
            ))}
          </div>

          {/* Return Type Toggle (for Distribution) */}
          {activeTab === 'DISTRIBUTION' && (
            <div className="quant-return-toggle">
              <button
                type="button"
                className={`quant-horizon-pill ${
                  returnType === 'SIMPLE' ? 'active' : ''
                }`}
                onClick={() => setReturnType('SIMPLE')}
                title="Discrete Simple Daily Return R_t = (P_t - P_{t-1}) / P_{t-1}"
              >
                SIMPLE
              </button>
              <button
                type="button"
                className={`quant-horizon-pill ${
                  returnType === 'LOG' ? 'active' : ''
                }`}
                onClick={() => setReturnType('LOG')}
                title="Continuous Log Daily Return r_t = ln(P_t / P_{t-1})"
              >
                LOG
              </button>
            </div>
          )}

          {/* Refresh Action */}
          <button
            type="button"
            className="quant-refresh-btn"
            onClick={() => {
              if (activeTab === 'DISTRIBUTION') {
                loadDistribution(ticker, horizon, returnType, true);
              } else if (activeTab === 'CORRELATION') {
                loadCorrelation(matrixTickers, horizon, true);
              } else {
                loadRolling(ticker, rollingMetric, rollingWindow, rollingTickerB, horizon, true);
              }
            }}
            title="Bypass cache and force recalculation"
          >
            ↻ REFRESH
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="quant-tab-content">
        {activeTab === 'DISTRIBUTION' && (
          <>
            {distError && (
              <ErrorMessage
                error={distError}
                onRetry={() => loadDistribution(ticker, horizon, returnType, true)}
              />
            )}
            {isDistLoading && !distData ? (
              <div className="quant-loading-view">
                COMPUTING EMPIRICAL DISTRIBUTION FOR {ticker}...
              </div>
            ) : distData ? (
              <ReturnDistributionInspector data={distData} />
            ) : null}
          </>
        )}

        {activeTab === 'CORRELATION' && (
          <>
            {matrixError && (
              <ErrorMessage
                error={matrixError}
                onRetry={() => loadCorrelation(matrixTickers, horizon, true)}
              />
            )}
            <CorrelationMatrixHeatmap
              data={matrixData}
              isLoading={isMatrixLoading}
              onUpdateTickers={(ts) => {
                setMatrixTickers(ts);
                loadCorrelation(ts, horizon, false);
              }}
            />
          </>
        )}

        {activeTab === 'ROLLING' && (
          <>
            {rollingError && (
              <ErrorMessage
                error={rollingError}
                onRetry={() =>
                  loadRolling(
                    ticker,
                    rollingMetric,
                    rollingWindow,
                    rollingTickerB,
                    horizon,
                    true
                  )
                }
              />
            )}
            <RollingCorrelationChart
              data={rollingData}
              isLoading={isRollingLoading}
              metric={rollingMetric}
              windowSize={rollingWindow}
              tickerA={ticker}
              tickerB={rollingTickerB}
              onChangeMetric={setRollingMetric}
              onChangeWindow={setRollingWindow}
              onChangeTickerB={setRollingTickerB}
              onRefresh={() =>
                loadRolling(
                  ticker,
                  rollingMetric,
                  rollingWindow,
                  rollingTickerB,
                  horizon,
                  true
                )
              }
            />
          </>
        )}
      </div>
    </div>
  );
};
