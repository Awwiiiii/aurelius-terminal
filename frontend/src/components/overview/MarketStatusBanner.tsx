import React from 'react';
import type { DataFreshness, MarketStatus } from '../../types/overview';

interface MarketStatusBannerProps {
  status: MarketStatus | null;
  freshness?: DataFreshness;
  cached?: boolean;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const MarketStatusBanner: React.FC<MarketStatusBannerProps> = ({
  status,
  freshness = 'DELAYED',
  cached = false,
  onRefresh,
  isRefreshing = false,
}) => {
  const getSessionBadgeClass = (state?: string) => {
    switch (state) {
      case 'REGULAR_OPEN':
        return 'session-open';
      case 'PRE_MARKET':
      case 'AFTER_HOURS':
        return 'session-extended';
      case 'WEEKEND':
      case 'CLOSED':
        return 'session-closed';
      case 'UNKNOWN':
      default:
        return 'session-unknown';
    }
  };

  const getSessionLabel = (state?: string) => {
    switch (state) {
      case 'REGULAR_OPEN':
        return 'REGULAR OPEN';
      case 'PRE_MARKET':
        return 'PRE-MARKET';
      case 'AFTER_HOURS':
        return 'AFTER-HOURS';
      case 'WEEKEND':
        return 'WEEKEND (CLOSED)';
      case 'CLOSED':
        return 'MARKET CLOSED';
      case 'UNKNOWN':
      default:
        return 'SESSION UNVERIFIED';
    }
  };

  return (
    <div className="market-status-banner">
      <div className="status-banner-left">
        <div className="status-indicator-group">
          <span className="region-tag">REGION: {status?.region || 'US'}</span>
          <div
            className={`session-pill ${getSessionBadgeClass(status?.session_state)}`}
          >
            <span className="status-dot-pulse"></span>
            <span className="session-state-text">
              {getSessionLabel(status?.session_state)}
            </span>
          </div>
        </div>

        {status?.session_message && (
          <div className="session-message-text">{status.session_message}</div>
        )}
      </div>

      <div className="status-banner-right">
        <div className="telemetry-metadata">
          <span className="telemetry-tag">
            TZ: {status?.exchange_timezone || 'America/New_York'}
          </span>
          <span className="telemetry-tag">{freshness}</span>
          {cached && <span className="telemetry-tag cached-tag">CACHED (60s)</span>}
          {status?.is_indicative && (
            <span className="telemetry-tag indicative-tag">INDICATIVE</span>
          )}
        </div>

        {onRefresh && (
          <button
            type="button"
            className="refresh-button"
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Refresh market telemetry & mover snapshots"
          >
            <span className={`refresh-icon ${isRefreshing ? 'spinning' : ''}`}>
              ⟳
            </span>
            <span>{isRefreshing ? 'REFRESHING...' : 'REFRESH'}</span>
          </button>
        )}
      </div>
    </div>
  );
};
