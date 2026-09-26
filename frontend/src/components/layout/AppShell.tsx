import React from 'react';

interface AppShellProps {
  children: React.ReactNode;
  headerCenter?: React.ReactNode;
  activeView?: 'OVERVIEW' | 'RESEARCH' | 'HISTORICAL' | 'QUANTITATIVE' | 'FINANCIALS' | 'FUNDAMENTALS';
  onViewChange?: (
    view: 'OVERVIEW' | 'RESEARCH' | 'HISTORICAL' | 'QUANTITATIVE' | 'FINANCIALS' | 'FUNDAMENTALS'
  ) => void;
}

export const AppShell: React.FC<AppShellProps> = ({
  children,
  headerCenter,
  activeView = 'OVERVIEW',
  onViewChange,
}) => {
  return (
    <div className="terminal-container">
      <header className="terminal-header">
        <div className="brand-group">
          <span className="brand-mark">◈</span>
          <div>
            <h1 className="brand-title">AURELIUS</h1>
            <span className="brand-subtitle">
              Financial Intelligence &amp; Research Terminal
            </span>
          </div>
        </div>

        <div className="workspace-mode-switch">
          <button
            type="button"
            className={`mode-switch-btn ${activeView === 'OVERVIEW' ? 'active' : ''}`}
            onClick={() => onViewChange && onViewChange('OVERVIEW')}
          >
            <span className="mode-btn-icon">◈</span>
            <span>MARKET OVERVIEW</span>
          </button>
          <button
            type="button"
            className={`mode-switch-btn ${activeView === 'RESEARCH' ? 'active' : ''}`}
            onClick={() => onViewChange && onViewChange('RESEARCH')}
          >
            <span className="mode-btn-icon">⌕</span>
            <span>SECURITY RESEARCH</span>
          </button>
          <button
            type="button"
            className={`mode-switch-btn ${activeView === 'HISTORICAL' ? 'active' : ''}`}
            onClick={() => onViewChange && onViewChange('HISTORICAL')}
          >
            <span className="mode-btn-icon">☵</span>
            <span>HISTORICAL ANALYSIS</span>
          </button>
          <button
            type="button"
            className={`mode-switch-btn ${activeView === 'QUANTITATIVE' ? 'active' : ''}`}
            onClick={() => onViewChange && onViewChange('QUANTITATIVE')}
          >
            <span className="mode-btn-icon">⨀</span>
            <span>QUANTITATIVE ANALYTICS</span>
          </button>
          <button
            type="button"
            className={`mode-switch-btn ${activeView === 'FINANCIALS' ? 'active' : ''}`}
            onClick={() => onViewChange && onViewChange('FINANCIALS')}
          >
            <span className="mode-btn-icon">▤</span>
            <span>FINANCIAL STATEMENTS</span>
          </button>
          <button
            type="button"
            className={`mode-switch-btn ${activeView === 'FUNDAMENTALS' ? 'active' : ''}`}
            onClick={() => onViewChange && onViewChange('FUNDAMENTALS')}
          >
            <span className="mode-btn-icon">☷</span>
            <span>FUNDAMENTAL ANALYSIS</span>
          </button>
        </div>

        {headerCenter && <div className="header-center">{headerCenter}</div>}

        <div className="header-meta">
          <span className="milestone-badge">M6 — FINANCIAL STATEMENTS</span>
          <span className="live-status">
            <span className="status-dot"></span>
            SYSTEM ONLINE
          </span>
        </div>
      </header>

      <main className="terminal-main">{children}</main>

      <footer className="terminal-footer">
        <div className="footer-disclaimer">
          <span>AURELIUS TERMINAL v0.1.0</span>
          <span>•</span>
          <span>Provider: Yahoo Finance (Unofficial Feed)</span>
          <span>•</span>
          <span>
            Notice: Quotes may be delayed 15–20 min. Adjusted closes reflect provider adjustments, not exact investor total return.
          </span>
        </div>
      </footer>
    </div>
  );
};
