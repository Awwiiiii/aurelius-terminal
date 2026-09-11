# ADR-0004: Historical Market Analysis Architecture & Quantitative Standards

## Context

In Milestones 1 through 3, AURELIUS implemented market quotes, basic historical OHLCV data retrieval, security/company entity resolution, and composite market overview monitoring.

Milestone 4 introduces dedicated historical market analysis. Users require interactive exploration of price trends, performance metrics, realized volatility, peak-to-trough drawdowns, moving average overlays, and benchmark comparison against the S&P 500 across nine configurable time horizons (`1M` to `MAX`).

Key architectural and financial challenges addressed:
1. **Price Series Dualism**: Corporate actions (e.g. stock splits and dividends) cause abrupt discontinuities in raw nominal prices, which distorts return and risk metrics if unadjusted. Conversely, technical moving averages and period extremes must reflect nominal traded execution prices.
2. **Terminology Accuracy**: Calling provider-adjusted returns "Total Return" would violate institutional standards, because provider `adj_close` represents a modeled split/dividend adjustment proxy and does not account for taxes, execution fees, or dividend reinvestment timing.
3. **Compound Growth Calculation**: Trading-day compounding across calendar-defined time horizons creates day-count distortion.
4. **Sample Volatility Observation Counts**: Sample standard deviation requires Bessel correction ($N-1$), which causes division-by-zero on fewer than 2 return observations (fewer than 3 price points).
5. **Moving Average Initialization**: Zero-indexed warm-up must be strictly defined so indicator formulas do not require extra observations or emit incorrect offsets.
6. **Benchmark Alignment**: Trading calendars vary across listings, requiring inner alignment and common base date rebasing.

---

## Decision

1. **Decoupled Pure Analytics Domain**:
   - Implemented mathematical modules in `aurelius.domain.analytics` (`returns.py`, `volatility.py`, `drawdowns.py`, `indicators.py`, `benchmark.py`) as pure functions with zero third-party dependencies beyond standard Python libraries (`decimal`, `math`, `datetime`).
2. **Strict Price Series Policy**:
   - **Adjusted Close (`adj_close`)**: Exclusively used for daily returns, cumulative series, calendar CAGR, win rates, realized volatility, and drawdowns.
   - **Raw Close (`close`)**: Exclusively used for technical indicators (SMA20, SMA50, SMA200, EMA20) and period extremes ($P_{\text{high}}$, $P_{\text{low}}$).
3. **Institutional Return Semantics**:
   - Cumulative period return is named `adjusted_price_return`.
   - Never designated as "Total Return".
4. **Calendar-Time CAGR Convention**:
   - $\text{CAGR} = (P_{\text{end}} / P_{\text{start}})^{(365.2425 / \text{calendar\_days})} - 1$ for $\text{calendar\_days} \ge 365$; emits `None` for sub-year horizons.
5. **Zero-Indexed Indicator Warm-Up**:
   - For $k=20$: observations 0..18 emit `None`; observation 19 is first $\text{SMA}_{20}$; $\text{EMA}_{20}$ initializes with $\text{SMA}_{20}$ at observation 19; observation 20 onward is recursive EMA.
6. **Inner-Aligned Benchmark Rebasing**:
   - Matches security and S&P 500 (`^GSPC`) bars on common trading dates. Earliest matched session serves as common base date rebased to 100.0.
7. **Three-Workspace Frontend AppShell**:
   - `[ ◈ MARKET OVERVIEW ]`
   - `[ ⌕ SECURITY RESEARCH ]`
   - `[ ☵ HISTORICAL ANALYSIS ]`
   - Interactive SVG terminal charting with candlestick/line toggles, indicator overlays, and sub-panel toggles (volume, underwater drawdown, rolling volatility).

---

## Consequences

- **Positive**:
  - Deterministic, institutionally sound quantitative analytics validated by automated test suites.
  - Complete protection against split-induced drawdown collapses (verified via synthetic split fixtures).
  - High frontend performance using pure SVG rendering without bloated third-party charting libraries.
  - Clean separation between core financial math, service orchestration, API serialization, and UI presentation.
- **Negative / Trade-offs**:
  - Indicator warm-up queries a historical buffer (~350 days) from the data provider, slightly increasing the payload size of historical provider calls. Mitigated by an in-memory 300s TTL service cache.
