import React from 'react';
import type { SecurityInfoResponse } from '../../types/company';

interface SecurityHeaderProps {
  security: SecurityInfoResponse;
  website?: string | null;
  onLaunchHistorical?: (ticker: string) => void;
  onLaunchQuantitative?: (ticker: string) => void;
  onLaunchFinancials?: (ticker: string) => void;
}

export const SecurityHeader: React.FC<SecurityHeaderProps> = ({
  security,
  website,
  onLaunchHistorical,
  onLaunchQuantitative,
  onLaunchFinancials,
}) => {
  return (
    <div className="security-header-panel">
      <div className="security-identity-row">
        <div className="security-title-group">
          <span className="security-ticker-large">{security.ticker}</span>
          <h2 className="security-name-primary">{security.name}</h2>
        </div>

        <div className="security-badge-group">
          <span
            className={`security-asset-tag tag-${security.asset_type.toLowerCase()}`}
          >
            {security.asset_type}
          </span>
          {security.exchange_display && (
            <span className="security-meta-tag venue-tag">
              {security.exchange_display}
            </span>
          )}
          <span className="security-meta-tag currency-tag">
            {security.currency}
          </span>
          {security.timezone && (
            <span className="security-meta-tag tz-tag" title="Listing Exchange Timezone">
              {security.timezone}
            </span>
          )}
          {website && (
            <a
              href={website}
              target="_blank"
              rel="noopener noreferrer"
              className="security-link-tag"
            >
              Website ↗
            </a>
          )}
          {onLaunchHistorical && (
            <button
              type="button"
              className="security-action-tag launch-historical-tag"
              onClick={() => onLaunchHistorical(security.ticker)}
              title="Launch full historical market analysis for this security"
            >
              ☵ HISTORICAL
            </button>
          )}
          {onLaunchQuantitative && (
            <button
              type="button"
              className="security-action-tag launch-quantitative-tag"
              onClick={() => onLaunchQuantitative(security.ticker)}
              title="Launch quantitative return distribution and risk analytics for this security"
            >
              ⨀ QUANTITATIVE
            </button>
          )}
          {onLaunchFinancials && (
            <button
              type="button"
              className="security-action-tag launch-financials-tag"
              onClick={() => onLaunchFinancials(security.ticker)}
              title="Launch financial statement infrastructure disclosures for this security"
            >
              ▤ FINANCIALS
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
