import React, { useCallback, useEffect, useState } from 'react';
import { fetchFinancialMatrix } from '../../api/financials';
import type {
  FinancialStatementMatrixResponse,
  FiscalPeriodType,
  StatementType,
} from '../../types/financials';
import { ErrorMessage } from '../ui/ErrorMessage';
import { TickerInput } from '../ui/TickerInput';
import { FinancialStatementTable } from './FinancialStatementTable';

interface FinancialStatementsViewProps {
  initialTicker?: string;
  onSelectTicker?: (ticker: string) => void;
}

export const FinancialStatementsView: React.FC<FinancialStatementsViewProps> = ({
  initialTicker = 'AAPL',
  onSelectTicker,
}) => {
  const [ticker, setTicker] = useState<string>(initialTicker);
  const [statementType, setStatementType] =
    useState<StatementType>('INCOME_STATEMENT');
  const [frequency, setFrequency] = useState<FiscalPeriodType>('ANNUAL');
  const [matrix, setMatrix] =
    useState<FinancialStatementMatrixResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const loadData = useCallback(
    async (sym: string, stType: StatementType, freq: FiscalPeriodType) => {
      setIsLoading(true);
      setError(null);

      try {
        const res = await fetchFinancialMatrix(sym, stType, freq);
        setMatrix(res);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setMatrix(null);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    loadData(ticker, statementType, frequency);
  }, [ticker, statementType, frequency, loadData]);

  const handleSelectTicker = (newTicker: string) => {
    const clean = newTicker.trim().toUpperCase();
    setTicker(clean);
    if (onSelectTicker) {
      onSelectTicker(clean);
    }
  };

  return (
    <div className="financials-view-layout">
      <div className="financials-header-panel">
        <div className="financials-controls-left">
          <TickerInput
            currentTicker={ticker}
            onSelectTicker={handleSelectTicker}
            isLoading={isLoading}
          />
        </div>

        <div className="financials-controls-right">
          <div className="statement-type-buttons">
            <button
              type="button"
              className={`statement-btn ${
                statementType === 'INCOME_STATEMENT' ? 'active' : ''
              }`}
              onClick={() => setStatementType('INCOME_STATEMENT')}
            >
              INCOME STATEMENT
            </button>
            <button
              type="button"
              className={`statement-btn ${
                statementType === 'BALANCE_SHEET' ? 'active' : ''
              }`}
              onClick={() => setStatementType('BALANCE_SHEET')}
            >
              BALANCE SHEET
            </button>
            <button
              type="button"
              className={`statement-btn ${
                statementType === 'CASH_FLOW' ? 'active' : ''
              }`}
              onClick={() => setStatementType('CASH_FLOW')}
            >
              CASH FLOW
            </button>
          </div>

          <div className="frequency-toggle-buttons">
            <button
              type="button"
              className={`freq-btn ${frequency === 'ANNUAL' ? 'active' : ''}`}
              onClick={() => setFrequency('ANNUAL')}
            >
              ANNUAL
            </button>
            <button
              type="button"
              className={`freq-btn ${frequency === 'QUARTERLY' ? 'active' : ''}`}
              onClick={() => setFrequency('QUARTERLY')}
            >
              QUARTERLY
            </button>
          </div>
        </div>
      </div>

      {error && (
        <ErrorMessage
          error={error}
          onRetry={() => loadData(ticker, statementType, frequency)}
        />
      )}

      {isLoading && (
        <div className="financials-loading-state">
          <span className="loading-spinner">◈</span>
          LOADING {frequency} {statementType.replace('_', ' ')} FOR {ticker}...
        </div>
      )}

      {!isLoading && !error && matrix && (
        <FinancialStatementTable matrix={matrix} />
      )}
    </div>
  );
};
