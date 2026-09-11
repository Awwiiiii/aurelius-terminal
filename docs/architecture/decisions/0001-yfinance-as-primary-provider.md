# ADR 0001: YFinance as Primary Market Data Provider in Milestone 1

## Context
AURELIUS requires market data feeds for security metadata, quote snapshots, and historical daily OHLCV bars.
Commercial providers (e.g., Bloomberg B-PIPE, Refinitiv, Financial Modeling Prep, Polygon) either require paid subscriptions, API keys, or have restrictive free-tier rate limits (e.g. 25–250 requests/day).
For local development, testing, and initial quantitative research, an accessible, zero-cost market data source is necessary.

## Decision
We select `yfinance` as the primary market data provider for Milestone 1, subject to the following architectural constraints:

1. **Strict Interface Decoupling**:
   `yfinance` is encapsulated inside `YFinanceProvider`, which implements the abstract `MarketDataProvider` interface. Neither the domain entities, nor the FastAPI route handlers, nor the frontend have any knowledge of or direct dependency on `yfinance`.
2. **Asynchronous Offloading**:
   Because `yfinance` uses synchronous, blocking `requests` calls, all provider interactions are offloaded to worker threads via `asyncio.to_thread` to maintain event-loop responsiveness.
3. **Explicit Unadjusted vs. Adjusted Separation**:
   Calls are executed with `auto_adjust=False` so that raw OHLC bars retain actual execution prices, while adjusted closes are captured in the separate `adj_close` field.
4. **Selective Transient Retries**:
   Retries are restricted to network timeouts and 5xx errors (1 retry with 2s delay). HTTP 429 rate limits, empty results (404), invalid inputs (400), and validation failures (422) are never retried.

## Trade-offs & Consequences
- **Pros**:
  - Zero cost; requires no API keys or developer accounts.
  - Comprehensive global coverage for major equities, ETFs, and indices.
  - Historical data available for decades.
- **Cons / Risks**:
  - Unofficial feed: Yahoo Finance may alter internal endpoint schemas or block IPs without notice.
  - Concurrency limitations: Known thread-safety quirks in `yfinance` under heavy concurrent scraping.
  - Latency: Scraping and parsing adds 300–800ms per request.
- **Mitigation**:
  - The provider registry and abstract interface enable seamless addition or replacement with official API providers (e.g. FMP, Polygon, Alpha Vantage) in future milestones without changing domain logic or API schemas.
