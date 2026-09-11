# ADR 0002: Security Search, Identity Context, and Polymorphic Company Profile Architecture

## Context
In Milestone 1, AURELIUS established market quote and historical OHLCV pipelines accessed via explicit ticker strings (`Quote` and `OHLCVSeries`).
In Milestone 2, researchers require:
1. Flexible search discovery (searching by company name, keywords, or special asset symbols).
2. Corporate entity intelligence (headquarters, employee headcount, business description).
3. Sector and industry categorization.
4. Robust handling of non-corporate assets (ETFs, mutual funds, indices, commodities) without breaking system assumptions.

Without careful architectural boundaries, systems risk:
- Confusing corporate entities with tradable securities and exchange listings.
- Generating 404 errors or throwing exceptions when users look up ETFs or indices because corporate profile fields are absent.
- Fabricating plausible defaults (e.g., defaulting missing currency to USD).
- Misrepresenting provider taxonomy strings as authoritative, licensed GICS classifications.

## Decision

1. **Conceptual Separation**:
   - `CompanyProfile`: Represents the legal operating commercial business.
   - `Security`: Represents the tradable financial instrument contract.
   - `Listing`: Venue-specific quotation convention (embedded in `Security` for M2 via `ticker`, `exchange`, `exchange_display`, `currency`, and `timezone`).
   - We do not build an institutional security master database in M2, but structure the models so a future multi-venue `Listing` model can be introduced without breaking `Security` or `CompanyProfile`.

2. **Polymorphic Non-Corporate Asset Handling**:
   - Non-corporate assets (ETFs, Indices, Crypto, Currencies) are valid `Security` records.
   - `MarketDataProvider.get_company_profile()` cleanly returns `None` for non-corporate assets or missing corporate records.
   - The API endpoints (`/market/security/{ticker}` and `/market/company/{ticker}`) return `200 OK` with `company_profile = null` and `is_operating_company = false`, accompanied by descriptive instrument overview messages, completely eliminating false 404 errors.

3. **Separation of Search Query Validation vs. Ticker Grammar**:
   - Search query validation (`validate_search_query`) accepts flexible text (1–60 characters, spaces preserved, mixed case, e.g. `"Apple Inc."`, `"S&P 500"`).
   - Ticker validation (`validate_ticker`) strictly enforces exchange routing grammar (`^[A-Z0-9.\-=^]{1,12}$`), supporting carets (`^GSPC`) and futures syntax (`ES=F`).

4. **Zero Plausible Fabrication**:
   - Missing provider currency is preserved as `Currency.UNKNOWN` or `None`; it is **never** defaulted to USD.
   - Missing metadata remains `None` throughout domain, API schemas, and frontend presentation.

5. **Taxonomy Provenance**:
   - Provider sector and industry strings are formally documented in API schemas and UI cards as "Yahoo Finance provider-supplied classification", explicitly clarifying that they are not authoritative GICS classifications.

## Trade-offs & Consequences
- **Pros**:
  - Eliminates crashes and 404 errors when researching non-corporate instruments (e.g. `SPY`, `^GSPC`).
  - Search UX is forgiving of spaces and natural language queries, while execution pipelines remain strictly typed.
  - Zero data corruption from fabricated default currencies or synthetic classifications.
  - Clear architectural upgrade path toward a full multi-venue security master in future milestones.
- **Cons / Risks**:
  - `yfinance.Search` API is undocumented and subject to provider changes; mitigated by ticker-fallback lookup if provider search returns empty for valid ticker strings.
