import React, { useEffect, useRef, useState } from 'react';
import { searchSecurities } from '../../api/search';
import type { SecuritySearchResultItem } from '../../types/search';
import { useDebounce } from '../../utils/debounce';

interface SearchBarProps {
  onSelectTicker: (ticker: string) => void;
  isLoading?: boolean;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSelectTicker }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SecuritySearchResultItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);
  const [searchError, setSearchError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const debouncedQuery = useDebounce(query, 300);

  // Global '/' hotkey to focus search bar
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      // If user presses '/' while not in an input/textarea
      if (
        e.key === '/' &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };

    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => {
      window.removeEventListener('keydown', handleGlobalKeyDown);
    };
  }, []);

  // Dismiss dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Perform search when debounced query changes
  useEffect(() => {
    const clean = debouncedQuery.trim();
    if (!clean) {
      setResults([]);
      setIsOpen(false);
      setSearchError(null);
      setIsSearching(false);
      return;
    }

    let active = true;
    setIsSearching(true);
    setSearchError(null);

    searchSecurities(clean, 8)
      .then((res) => {
        if (!active) return;
        setResults(res.results);
        setIsOpen(true);
        setSelectedIndex(-1);
      })
      .catch((err) => {
        if (!active) return;
        setSearchError(err?.message || 'Search failed');
        setResults([]);
        setIsOpen(true);
      })
      .finally(() => {
        if (active) {
          setIsSearching(false);
        }
      });

    return () => {
      active = false;
    };
  }, [debouncedQuery]);

  const handleSelect = (ticker: string) => {
    onSelectTicker(ticker);
    setIsOpen(false);
    setQuery('');
    setSelectedIndex(-1);
    inputRef.current?.blur();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      inputRef.current?.blur();
      return;
    }

    if (!isOpen || results.length === 0) {
      if (e.key === 'Enter' && query.trim()) {
        e.preventDefault();
        handleSelect(query.trim().toUpperCase());
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1 < results.length ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 >= 0 ? prev - 1 : results.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && selectedIndex < results.length) {
        handleSelect(results[selectedIndex].ticker);
      } else if (query.trim()) {
        handleSelect(query.trim().toUpperCase());
      }
    }
  };

  return (
    <div className="search-bar-wrapper" ref={containerRef}>
      <div className="search-input-group">
        <span className="search-icon">⌕</span>
        <input
          ref={inputRef}
          type="text"
          className="search-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search ticker, company name, ETF, or index... (Press '/' to focus)"
          autoComplete="off"
          spellCheck="false"
        />
        {isSearching && <span className="search-spinner">◈</span>}
        <span className="search-hotkey-badge">/</span>
      </div>

      {isOpen && (
        <div className="search-dropdown-menu">
          {searchError && (
            <div className="search-status-message error">{searchError}</div>
          )}

          {!searchError && results.length === 0 && !isSearching && (
            <div className="search-status-message">
              No securities found for "{debouncedQuery}"
            </div>
          )}

          {results.map((item, idx) => {
            const isSelected = idx === selectedIndex;
            return (
              <div
                key={`${item.ticker}-${idx}`}
                className={`search-result-item ${isSelected ? 'selected' : ''}`}
                onClick={() => handleSelect(item.ticker)}
                onMouseEnter={() => setSelectedIndex(idx)}
              >
                <div className="result-main-line">
                  <span className="result-ticker">{item.ticker}</span>
                  <span className={`result-asset-badge badge-${item.asset_type.toLowerCase()}`}>
                    {item.asset_type}
                  </span>
                  {item.exchange_display && (
                    <span className="result-exchange-badge">
                      {item.exchange_display}
                    </span>
                  )}
                </div>
                <div className="result-sub-line">
                  <span className="result-name">{item.name}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
