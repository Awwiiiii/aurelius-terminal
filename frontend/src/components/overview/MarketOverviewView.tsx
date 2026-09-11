import React, { useCallback, useEffect, useState } from 'react';
import { fetchMarketOverview } from '../../api/overview';
import type { MarketOverviewSnapshot } from '../../types/overview';
import { ErrorMessage } from '../ui/ErrorMessage';
import { BenchmarkRibbon } from './BenchmarkRibbon';
import { MarketMoversGrid } from './MarketMoversGrid';
import { MarketStatusBanner } from './MarketStatusBanner';

interface MarketOverviewViewProps {
  onSelectTicker: (ticker: string) => void;
}

export const MarketOverviewView: React.FC<MarketOverviewViewProps> = ({
  onSelectTicker,
}) => {
  const [snapshot, setSnapshot] = useState<MarketOverviewSnapshot | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const loadOverview = useCallback(async (forceRefresh = false) => {
    if (forceRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const data = await fetchMarketOverview(forceRefresh);
      setSnapshot(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadOverview(false);
  }, [loadOverview]);

  const handleBenchmarkSelect = (benchmarkId: string) => {
    const benchmarkSymbolMap: Record<string, string> = {
      SP500: '^GSPC',
      DOW: '^DJI',
      NASDAQ: '^IXIC',
      RUSSELL2000: '^RUT',
      VIX: '^VIX',
    };
    const symbol = benchmarkSymbolMap[benchmarkId] || benchmarkId;
    onSelectTicker(symbol);
  };

  if (isLoading && !snapshot) {
    return (
      <div className="overview-loading-state">
        <div className="terminal-spinner"></div>
        <div className="loading-text">
          INITIALIZING MARKET TELEMETRY &amp; BENCHMARK PIPELINES...
        </div>
      </div>
    );
  }

  if (error && !snapshot) {
    return (
      <div className="overview-error-state">
        <ErrorMessage error={error} onRetry={() => loadOverview(true)} />
      </div>
    );
  }

  return (
    <div className="market-overview-workspace">
      {snapshot && (
        <>
          <MarketStatusBanner
            status={snapshot.market_status}
            freshness={snapshot.freshness}
            cached={snapshot.cached}
            onRefresh={() => loadOverview(true)}
            isRefreshing={isRefreshing}
          />

          <BenchmarkRibbon
            benchmarks={snapshot.benchmarks}
            onSelectBenchmark={handleBenchmarkSelect}
          />

          <MarketMoversGrid
            gainers={snapshot.gainers}
            losers={snapshot.losers}
            active={snapshot.active}
            onSelectTicker={onSelectTicker}
          />

          <div className="overview-footer-meta">
            <span>SNAPSHOT TIME: {new Date(snapshot.fetched_at).toLocaleTimeString()} UTC</span>
            <span>•</span>
            <span>PROVIDER: {snapshot.provider.toUpperCase()}</span>
            <span>•</span>
            <span>FILTER POLICY: MIN PRICE $2.00, MIN VOL 100K (GAINERS/LOSERS)</span>
          </div>
        </>
      )}
    </div>
  );
};
