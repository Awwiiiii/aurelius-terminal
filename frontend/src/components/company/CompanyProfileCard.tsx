import React, { useState } from 'react';
import type { CompanyProfileResponse, SecurityInfoResponse } from '../../types/company';

interface CompanyProfileCardProps {
  security: SecurityInfoResponse;
  profile: CompanyProfileResponse | null;
  isOperatingCompany: boolean;
}

export const CompanyProfileCard: React.FC<CompanyProfileCardProps> = ({
  security,
  profile,
  isOperatingCompany,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // If the security is a non-corporate instrument (e.g. ETF, Index, Crypto)
  if (!isOperatingCompany || !profile) {
    return (
      <div className="profile-card-container non-corporate">
        <div className="profile-card-header">
          <div className="profile-header-title">
            <span className="profile-section-icon">◈</span>
            <h3>INSTRUMENT OVERVIEW & CLASSIFICATION</h3>
          </div>
          <span className="non-corporate-pill">NON-CORPORATE INSTRUMENT</span>
        </div>

        <div className="non-corporate-body">
          <div className="non-corporate-info-grid">
            <div className="info-stat-box">
              <span className="info-stat-label">INSTRUMENT CATEGORY</span>
              <span className="info-stat-value">{security.asset_type}</span>
            </div>
            <div className="info-stat-box">
              <span className="info-stat-label">LISTING EXCHANGE</span>
              <span className="info-stat-value">
                {security.exchange_display || security.exchange || '—'}
              </span>
            </div>
            <div className="info-stat-box">
              <span className="info-stat-label">BASE CURRENCY</span>
              <span className="info-stat-value">{security.currency}</span>
            </div>
            <div className="info-stat-box">
              <span className="info-stat-label">OPERATING ENTITY</span>
              <span className="info-stat-value">None (Composite / Fund / Index)</span>
            </div>
          </div>

          <p className="non-corporate-notice">
            {security.asset_type === 'ETF' && (
              <>
                <strong>Exchange-Traded Fund (ETF):</strong> This security represents a pooled
                investment vehicle holding a portfolio of underlying securities or commodities,
                rather than an operating commercial corporation. Consequently, standard corporate
                attributes (headquarters, employee headcount) do not apply.
              </>
            )}
            {security.asset_type === 'INDEX' && (
              <>
                <strong>Benchmark Index:</strong> This instrument represents a non-tradable or
                composite benchmark tracking a basket of securities or market segment. It is not an
                issuing corporate entity.
              </>
            )}
            {security.asset_type !== 'ETF' && security.asset_type !== 'INDEX' && (
              <>
                This instrument is classified as a {security.asset_type}. Corporate profile intelligence
                is not applicable for this instrument type.
              </>
            )}
          </p>
        </div>
      </div>
    );
  }

  // Operating Company Profile
  const description = profile.description || '';
  const shouldTruncate = description.length > 280;
  const displayText =
    shouldTruncate && !isExpanded
      ? `${description.slice(0, 280)}...`
      : description;

  const locationParts = [
    profile.address,
    profile.city,
    profile.state,
    profile.country,
  ].filter(Boolean);
  const locationString = locationParts.length > 0 ? locationParts.join(', ') : '—';

  return (
    <div className="profile-card-container">
      <div className="profile-card-header">
        <div className="profile-header-title">
          <span className="profile-section-icon">◈</span>
          <h3>COMPANY INTELLIGENCE & PROFILE</h3>
        </div>
        <div className="provider-provenance-tag">
          Feed: {profile.provider} (Retrieved: {new Date(profile.fetched_at).toLocaleTimeString()})
        </div>
      </div>

      <div className="profile-card-body">
        <div className="profile-stats-grid">
          <div className="info-stat-box">
            <span className="info-stat-label">SECTOR (PROVIDER CLASSIFICATION)</span>
            <span className="info-stat-value highlight">{profile.sector || '—'}</span>
            <span className="stat-sub-disclaimer">Yahoo Finance feed, not authoritative GICS</span>
          </div>

          <div className="info-stat-box">
            <span className="info-stat-label">INDUSTRY (PROVIDER CLASSIFICATION)</span>
            <span className="info-stat-value">{profile.industry || '—'}</span>
            <span className="stat-sub-disclaimer">Yahoo Finance feed, not authoritative GICS</span>
          </div>

          <div className="info-stat-box">
            <span className="info-stat-label">HEADQUARTERS</span>
            <span className="info-stat-value" title={locationString}>
              {locationString}
            </span>
          </div>

          <div className="info-stat-box">
            <span className="info-stat-label">EMPLOYEES</span>
            <span className="info-stat-value">
              {profile.employees !== null && profile.employees !== undefined
                ? profile.employees.toLocaleString()
                : '—'}
            </span>
          </div>
        </div>

        {description && (
          <div className="profile-description-section">
            <div className="description-header-label">BUSINESS OVERVIEW</div>
            <p className="profile-description-text">{displayText}</p>
            {shouldTruncate && (
              <button
                type="button"
                className="description-expand-btn"
                onClick={() => setIsExpanded(!isExpanded)}
              >
                {isExpanded ? 'Show Less ▴' : 'Read Full Overview ▾'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
