import React, { useCallback, useEffect, useState } from 'react';
import {
  fetchAdvancedFundamentals,
  fetchCommonSizeStatements,
  fetchFundamentalTrends,
} from '../../api/advancedFundamentals';
import { ApiError } from '../../api/client';
import type {
  AdvancedFundamentalsResponse,
  AdvancedPeriodType,
  CommonSizeStatementsResponse,
  FundamentalTrendsResponse,
  ProvenanceAuditTarget,
} from '../../types/advancedFundamentals';
import { ErrorMessage } from '../ui/ErrorMessage';
import { CommonSizeTableView } from './CommonSizeTableView';
import { DupontAnalysisView } from './DupontAnalysisView';
import { FundamentalTrendsView } from './FundamentalTrendsView';
import { ProvenanceModal } from './ProvenanceModal';
import { QualityDiagnosticsView } from './QualityDiagnosticsView';
import { RoicNopatPanel } from './RoicNopatPanel';

interface Props {
  ticker: string;
}

type SubSection = 'ROIC_NOPAT' | 'DUPONT' | 'DIAGNOSTICS' | 'COMMON_SIZE' | 'TRENDS';

export const AdvancedFundamentalsWorkspace: React.FC<Props> = ({ ticker }) => {
  const [periodType, setPeriodType] = useState<AdvancedPeriodType>('TTM');
  const [allowFallback, setAllowFallback] = useState<boolean>(false);
  const [activeSection, setActiveSection] = useState<SubSection>('ROIC_NOPAT');

  // Data states
  const [advancedData, setAdvancedData] = useState<AdvancedFundamentalsResponse | null>(null);
  const [commonSizeData, setCommonSizeData] = useState<CommonSizeStatementsResponse | null>(null);
  const [trendsData, setTrendsData] = useState<FundamentalTrendsResponse | null>(null);

  // Loading & error states
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [advError, setAdvError] = useState<Error | null>(null);
  const [csError, setCsError] = useState<Error | null>(null);
  const [trendsError, setTrendsError] = useState<Error | null>(null);

  // Provenance inspect state
  const [auditTarget, setAuditTarget] = useState<ProvenanceAuditTarget | null>(null);

  const loadData = useCallback(
    async (sym: string, pType: AdvancedPeriodType, fallback: boolean) => {
      setIsLoading(true);
      setAdvError(null);
      setCsError(null);
      setTrendsError(null);

      const [advRes, csRes, trendsRes] = await Promise.allSettled([
        fetchAdvancedFundamentals(sym, pType, null, null, fallback),
        fetchCommonSizeStatements(sym, pType, null, null),
        fetchFundamentalTrends(sym, pType),
      ]);

      if (advRes.status === 'fulfilled') {
        setAdvancedData(advRes.value);
      } else {
        setAdvancedData(null);
        setAdvError(advRes.reason instanceof Error ? advRes.reason : new Error(String(advRes.reason)));
      }

      if (csRes.status === 'fulfilled') {
        setCommonSizeData(csRes.value);
      } else {
        setCommonSizeData(null);
        setCsError(csRes.reason instanceof Error ? csRes.reason : new Error(String(csRes.reason)));
      }

      if (trendsRes.status === 'fulfilled') {
        setTrendsData(trendsRes.value);
      } else {
        setTrendsData(null);
        setTrendsError(trendsRes.reason instanceof Error ? trendsRes.reason : new Error(String(trendsRes.reason)));
      }

      setIsLoading(false);
    },
    []
  );

  useEffect(() => {
    loadData(ticker, periodType, allowFallback);
  }, [ticker, periodType, allowFallback, loadData]);

  // Helper to test if an error is a TTM 404
  const isTtm404 = (err: Error | null): boolean => {
    if (!err) return false;
    if (err instanceof ApiError && err.status === 404) return true;
    return err.message.includes('404') || err.message.includes('TTM') || err.message.includes('DATA_NOT_FOUND');
  };

  const renderTtm404Banner = (customMessage?: string) => (
    <div className="ttm-unavailable-card">
      <div className="ttm-card-header">
        <span className="ttm-icon">ℹ</span>
        <span className="ttm-title">TTM ANALYSIS UNAVAILABLE FOR {ticker}</span>
      </div>
      <div className="ttm-card-message">
        {customMessage ||
          'Sufficient aligned quarterly filing periods are currently unavailable from the market data provider to reconstruct trailing 12-month flows.'}
      </div>
      <div className="ttm-quick-switch">
        <span>Suggested action: </span>
        <button
          type="button"
          className="ttm-switch-btn"
          onClick={() => setPeriodType('ANNUAL')}
        >
          SWITCH TO ANNUAL
        </button>
        <button
          type="button"
          className="ttm-switch-btn"
          onClick={() => setPeriodType('QUARTERLY')}
        >
          SWITCH TO QUARTERLY
        </button>
      </div>
    </div>
  );

  return (
    <div className="advanced-workspace-layout">
      {/* Global Control Bar */}
      <div className="advanced-controls-bar">
        <div className="controls-left">
          <div className="controls-period-group">
            <span className="control-label">PERIOD FREQUENCY:</span>
            <div className="period-radio-group">
              <label className={`radio-label ${periodType === 'TTM' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="advanced-period"
                  value="TTM"
                  checked={periodType === 'TTM'}
                  onChange={() => setPeriodType('TTM')}
                />
                <span>TTM</span>
              </label>

              <label className={`radio-label ${periodType === 'ANNUAL' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="advanced-period"
                  value="ANNUAL"
                  checked={periodType === 'ANNUAL'}
                  onChange={() => setPeriodType('ANNUAL')}
                />
                <span>ANNUAL</span>
              </label>

              <label className={`radio-label ${periodType === 'QUARTERLY' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="advanced-period"
                  value="QUARTERLY"
                  checked={periodType === 'QUARTERLY'}
                  onChange={() => setPeriodType('QUARTERLY')}
                />
                <span>QUARTERLY</span>
              </label>
            </div>
          </div>

          {/* Point-in-Time Fallback Checkbox */}
          <div className="controls-fallback-group">
            <label
              className="fallback-checkbox-label"
              title="Allow point-in-time ending balance sheet fallback when prior beginning period is missing"
            >
              <input
                type="checkbox"
                checked={allowFallback}
                onChange={(e) => setAllowFallback(e.target.checked)}
              />
              <span className="fallback-text">ALLOW POINT-IN-TIME FALLBACK</span>
            </label>
            {allowFallback && (
              <span className="fallback-active-pill" title="Point-in-time fallback is enabled in API request">
                PIT FALLBACK ENABLED
              </span>
            )}
          </div>
        </div>

        <div className="controls-right">
          <div className="sub-section-tabs">
            <button
              type="button"
              className={`sub-tab-btn ${activeSection === 'ROIC_NOPAT' ? 'active' : ''}`}
              onClick={() => setActiveSection('ROIC_NOPAT')}
            >
              ROIC &amp; NOPAT
            </button>
            <button
              type="button"
              className={`sub-tab-btn ${activeSection === 'DUPONT' ? 'active' : ''}`}
              onClick={() => setActiveSection('DUPONT')}
            >
              DUPONT ANALYSIS
            </button>
            <button
              type="button"
              className={`sub-tab-btn ${activeSection === 'DIAGNOSTICS' ? 'active' : ''}`}
              onClick={() => setActiveSection('DIAGNOSTICS')}
            >
              QUALITY DIAGNOSTICS
            </button>
            <button
              type="button"
              className={`sub-tab-btn ${activeSection === 'COMMON_SIZE' ? 'active' : ''}`}
              onClick={() => setActiveSection('COMMON_SIZE')}
            >
              COMMON-SIZE
            </button>
            <button
              type="button"
              className={`sub-tab-btn ${activeSection === 'TRENDS' ? 'active' : ''}`}
              onClick={() => setActiveSection('TRENDS')}
            >
              FUNDAMENTAL TRENDS
            </button>
          </div>
        </div>
      </div>

      {/* Loading Bar */}
      {isLoading && (
        <div className="financials-loading-state">
          <span className="loading-spinner">◈</span>
          COMPUTING {periodType} ADVANCED FUNDAMENTALS DOSSIER FOR {ticker}...
        </div>
      )}

      {/* Section Content */}
      {!isLoading && (
        <div className="advanced-sections-container">
          {/* 1. ROIC & NOPAT */}
          {activeSection === 'ROIC_NOPAT' && (
            <>
              {advError ? (
                isTtm404(advError) ? (
                  renderTtm404Banner(advError.message)
                ) : (
                  <ErrorMessage
                    error={advError}
                    onRetry={() => loadData(ticker, periodType, allowFallback)}
                  />
                )
              ) : advancedData ? (
                <RoicNopatPanel
                  data={advancedData}
                  allowFallback={allowFallback}
                  onInspectProvenance={(t) => setAuditTarget(t)}
                />
              ) : null}
            </>
          )}

          {/* 2. DuPont Analysis */}
          {activeSection === 'DUPONT' && (
            <>
              {advError ? (
                isTtm404(advError) ? (
                  renderTtm404Banner(advError.message)
                ) : (
                  <ErrorMessage
                    error={advError}
                    onRetry={() => loadData(ticker, periodType, allowFallback)}
                  />
                )
              ) : advancedData ? (
                <DupontAnalysisView
                  data={advancedData}
                  allowFallback={allowFallback}
                  onInspectProvenance={(t) => setAuditTarget(t)}
                />
              ) : null}
            </>
          )}

          {/* 3. Quality Diagnostics */}
          {activeSection === 'DIAGNOSTICS' && (
            <>
              {advError ? (
                isTtm404(advError) ? (
                  renderTtm404Banner(advError.message)
                ) : (
                  <ErrorMessage
                    error={advError}
                    onRetry={() => loadData(ticker, periodType, allowFallback)}
                  />
                )
              ) : advancedData ? (
                <QualityDiagnosticsView
                  data={advancedData}
                  allowFallback={allowFallback}
                  onInspectProvenance={(t) => setAuditTarget(t)}
                />
              ) : null}
            </>
          )}

          {/* 4. Common-Size Statements */}
          {activeSection === 'COMMON_SIZE' && (
            <>
              {csError ? (
                isTtm404(csError) ? (
                  renderTtm404Banner(csError.message)
                ) : (
                  <ErrorMessage
                    error={csError}
                    onRetry={() => loadData(ticker, periodType, allowFallback)}
                  />
                )
              ) : commonSizeData ? (
                <CommonSizeTableView
                  data={commonSizeData}
                  onInspectProvenance={(t) => setAuditTarget(t)}
                />
              ) : null}
            </>
          )}

          {/* 5. Fundamental Trends */}
          {activeSection === 'TRENDS' && (
            <>
              {trendsError ? (
                isTtm404(trendsError) ? (
                  renderTtm404Banner(trendsError.message)
                ) : (
                  <ErrorMessage
                    error={trendsError}
                    onRetry={() => loadData(ticker, periodType, allowFallback)}
                  />
                )
              ) : trendsData ? (
                <FundamentalTrendsView
                  data={trendsData}
                  onInspectProvenance={(t) => setAuditTarget(t)}
                />
              ) : null}
            </>
          )}
        </div>
      )}

      {/* Auditable Provenance Inspector Modal */}
      {auditTarget && (
        <ProvenanceModal
          auditTarget={auditTarget}
          onClose={() => setAuditTarget(null)}
        />
      )}
    </div>
  );
};
