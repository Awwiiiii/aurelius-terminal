import { useCallback, useEffect, useState } from 'react';
import './App.css';
import { fetchLast30DaysOHLCV, fetchQuote } from './api/market';
import { AppShell } from './components/layout/AppShell';
import { OHLCVTable } from './components/market/OHLCVTable';
import { QuoteCard } from './components/market/QuoteCard';
import { ErrorMessage } from './components/ui/ErrorMessage';
import { TickerInput } from './components/ui/TickerInput';
import type { OHLCVResponse, QuoteResponse } from './types/market';

export function App() {
  const [ticker, setTicker] = useState<string>('AAPL');
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [ohlcv, setOhlcv] = useState<OHLCVResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const loadData = useCallback(async (symbol: string) => {
    setIsLoading(true);
    setError(null);

    try {
      // Call quote and 30-day historical bars in parallel
      const [quoteRes, ohlcvRes] = await Promise.all([
        fetchQuote(symbol),
        fetchLast30DaysOHLCV(symbol),
      ]);
      setQuote(quoteRes);
      setOhlcv(ohlcvRes);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setQuote(null);
      setOhlcv(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(ticker);
  }, [ticker, loadData]);

  const handleSelectTicker = (newTicker: string) => {
    setTicker(newTicker);
  };

  return (
    <AppShell>
      <TickerInput
        currentTicker={ticker}
        onSelectTicker={handleSelectTicker}
        isLoading={isLoading}
      />

      {error && <ErrorMessage error={error} onRetry={() => loadData(ticker)} />}

      {isLoading && !quote && (
        <div className="loading-state">
          LOADING FINANCIAL DATA FOR {ticker}...
        </div>
      )}

      {quote && <QuoteCard quote={quote} />}

      {ohlcv && ohlcv.bars && ohlcv.bars.length > 0 && (
        <OHLCVTable series={ohlcv} />
      )}
    </AppShell>
  );
}

export default App;
