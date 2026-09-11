import React from 'react';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  return (
    <div className="terminal-container">
      <header className="terminal-header">
        <div className="brand-group">
          <span className="brand-mark">◈</span>
          <div>
            <h1 className="brand-title">AURELIUS</h1>
            <span className="brand-subtitle">Financial Intelligence & Research Terminal</span>
          </div>
        </div>
        <div className="header-meta">
          <span className="milestone-badge">M1 — MARKET DATA</span>
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
