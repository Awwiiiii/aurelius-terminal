# ADR 0003: Market Overview Workspace, Canonical Benchmarks, and Indicative Session Telemetry

## Context
Milestone 1 and Milestone 2 established ticker-level research pipelines (`Quote`, `OHLCVSeries`, `Security`, `CompanyProfile`).
In Milestone 3, AURELIUS expands from single-security analysis into broad market intelligence:
1. Macroeconomic and benchmark tracking across core indices (S&P 500, Dow Jones, Nasdaq, Russell 2000, and CBOE VIX).
2. Market-wide session movers (top percentage gainers, top percentage losers, and volume leaders).
3. Market operational session telemetry (regular session, pre-market, after-hours, closed, weekend).

Without deliberate financial and architectural constraints:
- Volatility indicators (VIX) might be conflated with currency-priced equities, improperly showing dollar signs and confusing implied volatility with equity price.
- Missing volume data from provider feeds might be defaulted to zero, confusing missing telemetry with verified trading halts.
- Market capitalization might be reconstructed using naive price $\times$ shares calculations, conflicting with reported market cap.
- High-frequency market-overview polling could cause upstream provider rate-limiting (HTTP 429).
- Market session status could assert that markets are open on weekdays without holiday calendar verification.

## Decision

1. **Benchmark Universe Decoupling**:
   - Pure domain `BenchmarkDefinition` decouples canonical benchmark identities (`SP500`, `DOW`, `NASDAQ`, `RUSSELL2000`, `VIX`) from provider routing symbols (`^GSPC`, `^DJI`, `^IXIC`, `^RUT`, `^VIX`).
   - The `is_currency_priced` domain flag identifies volatility/sentiment indices.
   - For `VIX`, `is_currency_priced = False` and `currency = Currency.UNKNOWN`. The frontend strictly formats VIX as index points (`pts`) without currency symbols (`$`).

2. **Strict Volume and Market Cap Semantics**:
   - Volume is represented as an integer whole-share count or `None` if missing. It is **never** converted to or displayed as `0`.
   - Market capitalization is sourced strictly from provider-reported `marketCap` (or `None`). AURELIUS does not reconstruct market cap in M3.
   - Mover category overlap across Gainers and Active is explicitly permitted and preserved; deduplication operates strictly per category.
   - Presentation noise filters ($\ge \$2.00$ price, $\ge 100,000$ volume for gainers/losers) are labeled as UI presentation filters, not universal financial criteria.

3. **Safe Session Telemetry Fallback Hierarchy**:
   - Provider operational session telemetry is queried via `yf.Market("US").status`.
   - In the event of provider errors or unverified session state:
     - Weekend check (Saturday/Sunday in `America/New_York`) $\rightarrow$ `WEEKEND`.
     - Weekday $\rightarrow$ `UNKNOWN` (never assert `REGULAR_OPEN` on weekdays without verified exchange holiday calendar validation).

4. **Concurrency-Safe In-Memory Snapshot Cache**:
   - A service-level TTL cache (`MarketOverviewService`) caches composite snapshots for 60 seconds.
   - Protected by `asyncio.Lock` to prevent concurrent cache stampedes and redundant provider hits.
   - Forced refresh (`force_refresh=True`) allows immediate on-demand bypass.

## Trade-offs & Consequences
- **Pros**:
  - Financial fidelity: VIX is correctly treated as implied volatility index points, not currency.
  - Zero data fabrication: missing volume remains `null`, preventing false zero-liquidity signals.
  - Downstream rate-limit protection: 60s TTL cache prevents 429 provider errors during rapid navigation.
  - Fail-safe operational telemetry: no false claims of open markets on holidays.
- **Cons / Limitations**:
  - Without a licensed holiday calendar feed, weekday provider outages result in `UNKNOWN` status rather than authoritative session status.
