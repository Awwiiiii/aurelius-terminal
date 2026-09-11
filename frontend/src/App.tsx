import { useCallback, useEffect, useState } from 'react';
import './App.css';
import { getSecurityDetail } from './api/company';
import { fetchLast30DaysOHLCV, fetchQuote } from './api/market';
import { CompanyProfileCard } from './components/company/CompanyProfileCard';
import { SecurityHeader } from './components/company/SecurityHeader';
import { HistoricalAnalysisView } from './components/historical/HistoricalAnalysisView';
import { AppShell } from './components/layout/AppShell';
import { OHLCVTable } from './components/market/OHLCVTable';
import { QuoteCard } from './components/market/QuoteCard';
import { MarketOverviewView } from './components/overview/MarketOverviewView';
import { SearchBar } from './components/search/SearchBar';
import { ErrorMessage } from './components/ui/ErrorMessage';
import { TickerInput } from './components/ui/TickerInput';
import type { SecurityDetailResponse } from './types/company';
import type { OHLCVResponse, QuoteResponse } from './types/market';

export function App() {
  const [activeView, setActiveView] = useState<
    'OVERVIEW' | 'RESEARCH' | 'HISTORICAL'
  >(
    'OVERVIEW'
  );
  const [ticker, setTicker] = useState<string>('AAPL');
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [ohlcv, setOhlcv] = useState<OHLCVResponse | null>(null);
  const [securityDetail, setSecurityDetail] =
    useState<SecurityDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const loadData = useCallback(async (symbol: string) => {
    setIsLoading(true);
    setError(null);

    try {
      // Call quote, historical bars, and security metadata concurrently
      const [quoteRes, ohlcvRes, secDetailRes] = await Promise.all([
        fetchQuote(symbol),
        fetchLast30DaysOHLCV(symbol),
        getSecurityDetail(symbol),
      ]);
      setQuote(quoteRes);
      setOhlcv(ohlcvRes);
      setSecurityDetail(secDetailRes);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setQuote(null);
      setOhlcv(null);
      setSecurityDetail(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeView === 'RESEARCH') {
      loadData(ticker);
    }
  }, [ticker, activeView, loadData]);

  const handleSelectTicker = (newTicker: string) => {
    setTicker(newTicker);
    setActiveView('RESEARCH');
  };

  const handleLaunchHistorical = (newTicker: string) => {
    setTicker(newTicker);
    setActiveView('HISTORICAL');
  };

  return (
    <AppShell
      activeView={activeView}
      onViewChange={setActiveView}
      headerCenter={<SearchBar onSelectTicker={handleSelectTicker} />}
    >
      {activeView === 'OVERVIEW' ? (
        <MarketOverviewView onSelectTicker={handleSelectTicker} />
      ) : activeView === 'HISTORICAL' ? (
        <HistoricalAnalysisView
          initialTicker={ticker}
          onSelectTicker={(s) => setTicker(s)}
        />
      ) : (
        <>
          <TickerInput
            key={ticker}
            currentTicker={ticker}
            onSelectTicker={handleSelectTicker}
            isLoading={isLoading}
          />

          {error && (
            <ErrorMessage error={error} onRetry={() => loadData(ticker)} />
          )}

          {isLoading && !quote && (
            <div className="loading-state">
              LOADING FINANCIAL DATA &amp; PROFILE FOR {ticker}...
            </div>
          )}

          {securityDetail && (
            <SecurityHeader
              security={securityDetail.security}
              website={securityDetail.company_profile?.website}
              onLaunchHistorical={handleLaunchHistorical}
            />
          )}

          {quote && <QuoteCard quote={quote} />}

          {securityDetail && (
            <CompanyProfileCard
              security={securityDetail.security}
              profile={securityDetail.company_profile ?? null}
              isOperatingCompany={securityDetail.is_operating_company}
            />
          )}

          {ohlcv && ohlcv.bars && ohlcv.bars.length > 0 && (
            <OHLCVTable series={ohlcv} />
          )}
        </>
      )}
    </AppShell>
  );
}

export default App;
