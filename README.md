# AURELIUS — Financial Intelligence & Research Terminal

AURELIUS is an educational and portfolio financial intelligence and quantitative research terminal inspired by institutional analytical workflows found in professional financial research platforms. 

It is an entirely independent, clean-room implementation designed to demonstrate rigorous financial software engineering, mathematical statistics, domain-driven architecture, and modern full-stack web development. AURELIUS does not reproduce, incorporate, or interface with proprietary Bloomberg, Capital IQ, Refinitiv, or other proprietary platforms, systems, interfaces, or data feeds.

---

## 1. Overview

AURELIUS is developed under a strict engineering philosophy:

> **CORRECTNESS > COMPLETENESS > SPEED**

Modern financial systems require uncompromising mathematical integrity, defensive validation, and clear domain boundaries. In AURELIUS:
- Every financial formula is documented in dedicated reference handbooks before implementation.
- Every statistical estimator explicitly declares its sample vs. population conventions, Bessel's corrections, and degrees-of-freedom guardrails.
- Financial data engineering distinguishes between raw transaction prices and retroactive provider adjustments.
- Application logic is isolated into pure domain entities, decoupled application services, infrastructure provider adapters, and typed HTTP interfaces.

The project currently encompasses completed Milestones 0 through 5, delivering end-to-end capabilities from market data ingestion and company intelligence to historical performance attribution and an institutional-grade quantitative analytics engine.

---

## 2. Current Capabilities

The terminal provides integrated modules across five completed foundational milestones:

### M0 — Architecture & Project Foundation
- **Layered Clean Architecture**: Strict separation of Domain (`domain/`), Application Services (`services/`), Data Providers (`providers/`), API Transport (`api/v1/`), and User Interface (`frontend/`).
- **Domain Error Hierarchy**: Structured exceptions (`AureliusError`, `NotFoundError`, `ProviderError`, `DataAlignmentError`, `InsufficientDataError`) mapped directly to deterministic HTTP status codes and structured client error responses.
- **Type-Safe Configuration**: Centralized settings management using `pydantic-settings` reading from `.env` and environment variables.

### M1 — Market Data Infrastructure
- **OHLCV Data Engine**: Daily bar models with chronological ordering and strict price validation (`high >= low`, `high >= open`, `high >= close`, `volume >= 0`).
- **Provider Normalization**: Resilient provider adapter for Yahoo Finance (`yfinance`) with payload normalization and error recovery.
- **Real-Time Snapshot Quotes**: Last price, bid, ask, change, percentage change, and volume metrics.
- **Interactive Charting**: Canvas-based candlestick charting with TradingView Lightweight Charts integration.

### M2 — Security Search & Company Profiles
- **Multi-Asset Ticker Search**: Real-time ticker search with input debouncing and symbol normalization.
- **Corporate Profiles**: Comprehensive profile data including sector, industry, corporate officers, business descriptions, exchange listings, share counts, and capitalization statistics.

### M3 — Market Overview & Telemetry
- **Macro Benchmark Dashboard**: Real-time monitoring of major equity benchmarks (S&P 500 `^GSPC`, Nasdaq 100 `^IXIC`, Dow Jones `^DJI`, Russell 2000 `^RUT`), 10-Year Treasury Yields (`^TNX`), and the Cboe Volatility Index (`^VIX`).
- **Market Movers**: Automated tracking of top gainers, top losers, and most active securities.
- **Market Breadth & Sector Monitoring**: Visual sector performance tracking and high-level market health metrics.

### M4 & M4.1 — Historical Market Analysis
- **Multi-Horizon Analysis**: Flexible evaluation across standard horizons (`1M`, `3M`, `6M`, `1Y`, `5Y`, `Max`).
- **Moving Averages on Raw Close**: Simple Moving Averages (`SMA 20`, `SMA 50`, `SMA 200`) and Exponential Moving Average (`EMA 20`) computed strictly on actual transaction close prices (`close`) to preserve technical support/resistance levels.
- **Drawdown & Peak Analytics**: Dynamic peak-to-date tracking, current drawdown, maximum drawdown (`MDD`) with deterministic tie-breaking, and peak/trough calendar date localization.
- **Period Performance Attribution**: Period high/low extremes and calendar-time Compound Annual Growth Rate (`CAGR`) computed strictly for time spans $\ge 1$ calendar year (withheld for sub-year horizons).
- **Benchmark Comparative Tracking**: Relative normalized performance comparison against S&P 500 (`^GSPC`) aligned to a synchronized common base date.
- **Stabilized SVG Visualizations**: Dedicated sub-panels for rolling volatility, multi-series SVG overlays, and synchronized crosshair scrubbing.

### M5 — Quantitative Analytics Foundation
- **Single-Ticker Statistical Profile**: Complete univariate descriptive statistics, percentile distributions, and tail risk metrics.
- **Multi-Ticker Cross-Asset Analysis**: Pairwise covariance and Pearson correlation matrix calculation across configurable multi-asset baskets.
- **Deterministic Distribution Engine**: Frequency histogram binning using Freedman-Diaconis adaptive sizing with zero data fabrication.
- **Rolling Dynamics**: Configurable rolling-window statistics with zero-indexed warm-up periods.
- **Strict Data Alignment**: Calendar date inner-join alignment across disparate security trading calendars.

---

## 3. Architecture

AURELIUS follows Domain-Driven Design (DDD) principles with unidirectional dependencies:

```
aurelius/
├── backend/
│   ├── aurelius/
│   │   ├── api/v1/         # FastAPI REST endpoints & Pydantic response schemas
│   │   ├── domain/         # Pure domain entities, value objects & financial analytics
│   │   │   ├── analytics/  # Returns, statistics, quantiles, distributions, multivariate, rolling
│   │   │   └── entities/   # Market, company, historical, and quantitative entities
│   │   ├── infrastructure/ # Logging, caching, and telemetry primitives
│   │   ├── providers/      # External provider adapters (Yahoo Finance / yfinance)
│   │   ├── services/       # Application orchestrators coordinating retrieval and analytics
│   │   └── settings.py     # Pydantic-settings configuration loader
│   └── tests/
│       ├── integration/    # Provider integration and network-dependent tests
│       └── unit/           # Comprehensive domain math, service, and API tests
├── frontend/
│   ├── src/
│   │   ├── api/            # Typed API client contracts
│   │   ├── components/     # Specialized workspace UI components
│   │   │   ├── historical/ # Historical charts, moving averages, and drawdown panels
│   │   │   └── quantitative/# Quant workbench, statistics tables, histogram, correlation matrix
│   │   ├── pages/          # Terminal views (Search, Overview, History, Quantitative)
│   │   └── index.css       # Monochromatic institutional design system (Vanilla CSS)
│   └── vite.config.ts      # Vite server configuration with reverse proxy
├── docs/                   # Architecture decision records and Finance Handbook
└── scripts/                # Setup and automation scripts
```

### Key Architectural Boundaries:
1. **Pure Domain Analytics**: The `domain/analytics/` module is entirely decoupled from external frameworks, databases, and I/O. Functions accept primitive float/int sequences and return typed domain objects.
2. **Provider Isolation**: Third-party APIs (`yfinance`) are encapsulated within `providers/`. Changes in external schema formats never propagate beyond the adapter layer.
3. **Application Services**: The `services/` layer handles asynchronous orchestration, caching, inner data alignment, and dispatching computational workloads.
4. **Transport Layer**: The `api/v1/` endpoints enforce OpenAPI input validation and output schema serialization using Pydantic v2.

---

## 4. Technology Stack

| Layer | Component | Technology | Rationale |
|---|---|---|---|
| **Backend Runtime** | Language | Python 3.12 | Modern type hints, high-performance runtime features |
| **Package Management** | Dependency Manager | uv | Deterministic lockfiles and fast dependency resolution |
| **API Framework** | REST API | FastAPI | Async ASGI framework with native OpenAPI schema generation |
| **Data Validation** | Schema Validation | Pydantic v2 | High-performance C-based data validation and parsing |
| **HTTP Client** | Async Requests | HTTPX | Asynchronous HTTP client for provider communication |
| **Data Normalization** | Series Processing | pandas | Robust time series alignment and tabular manipulation |
| **Market Data Feed** | Data Adapter | yfinance | Development feed for historical daily OHLCV and quotes |
| **Frontend Framework** | UI Library | React 19 + TypeScript | Strict static typing, modular component architecture |
| **Build Tool** | Bundler | Vite | Fast HMR and optimized production bundling |
| **Styling** | Design System | Vanilla CSS | High-contrast institutional dark mode without utility framework bloat |
| **Financial Charting** | Canvas Charts | TradingView Lightweight Charts | High-performance canvas-based financial candlestick rendering |
| **Testing & Quality** | Test Runner | pytest, pytest-asyncio | Full test coverage for async and sync Python code |
| **Code Quality** | Linting & Formatting | Ruff | Ultra-fast Python linting and formatting |
| **Frontend QA** | Type Checking | tsc, oxlint | Static TypeScript verification and fast frontend linting |

---

## 5. Quantitative Analytics

Milestone 5 implements a production-grade mathematical foundation for financial time series analysis:

### Return Calculations
- **Simple Return**: $R_t = \frac{P_t - P_{t-1}}{P_{t-1}}$
- **Log Return**: $r_t = \ln\left(\frac{P_t}{P_{t-1}}\right)$
- **Cumulative Compounded Return**: $\prod_{t=1}^T (1 + R_t) - 1$

### Univariate Descriptive Statistics
- **Arithmetic Mean**: $\bar{R} = \frac{1}{N} \sum_{i=1}^N R_i$
- **Geometric Mean**: $\left(\prod_{i=1}^N (1 + R_i)\right)^{1/N} - 1$ (computed on gross returns $1 + R_i$)
- **Sample Variance**: $s^2 = \frac{1}{N - 1} \sum_{i=1}^N (R_i - \bar{R})^2$ (unbiased with Bessel's correction $N-1$)
- **Population Variance**: $\sigma^2 = \frac{1}{N} \sum_{i=1}^N (R_i - \mu)^2$
- **Sample Standard Deviation**: $s = \sqrt{s^2}$
- **Population Standard Deviation**: $\sigma = \sqrt{\sigma^2}$
- **Median**: Middle value of sorted observations (or mean of two central values for even $N$)
- **Range**: $\max(R) - \min(R)$
- **Interquartile Range (IQR)**: $Q_{75} - Q_{25}$ using Hyndman-Fan Method 7 linear interpolation
- **Mean Absolute Deviation (MAD)**: $\frac{1}{N} \sum_{i=1}^N |R_i - \text{Median}(R)|$

### Shape & Higher Moments
- **Fisher-Pearson Sample Skewness**:
  $$G_1 = \frac{N}{(N-1)(N-2)} \sum_{i=1}^N \left(\frac{R_i - \bar{R}}{s}\right)^3 \quad (N \ge 3)$$
- **Sample Excess Kurtosis**:
  $$G_2 = \frac{N(N+1)}{(N-1)(N-2)(N-3)} \sum_{i=1}^N \left(\frac{R_i - \bar{R}}{s}\right)^4 - \frac{3(N-1)^2}{(N-2)(N-3)} \quad (N \ge 4)$$
  *(Evaluates to 0 for a standard normal distribution. Strictly returns `None` when $N < 4$.)*

### Distribution & Histogram Engine
- **Percentiles**: Continuous quantile interpolation using Method 7 ($h = (N - 1)p + 1$, linear weighting between adjacent ranks).
- **Freedman-Diaconis Bin Width**:
  $$h = 2 \times \text{IQR} \times N^{-1/3}$$
  Determines optimal histogram bin count adaptively based on sample size and spread, guarded against zero IQR degeneracy.

### Multivariate & Systematic Risk
- **Sample Covariance**:
  $$\text{Cov}(X, Y) = \frac{1}{N-1} \sum_{i=1}^N (X_i - \bar{X})(Y_i - \bar{Y})$$
- **Pearson Correlation**:
  $$r_{xy} = \frac{\text{Cov}(X, Y)}{s_x s_y}$$
- **Correlation Matrix**: Deterministic symmetric $M \times M$ matrix with unit diagonal ($r_{ii} = 1.0$), computed over the pairwise common date intersection.
- **Market Beta**:
  $$\beta = \frac{\text{Cov}(R_i, R_m)}{s_m^2}$$
- **Tracking Error**: Sample standard deviation of active return differentials ($R_i - R_b$), annualized via $\sqrt{252}$:
  $$\text{TE} = s(R_i - R_b) \times \sqrt{252}$$

### Rolling Dynamics & Alignment
- **Rolling Statistics**: Rolling mean, rolling annualized volatility ($s \times \sqrt{252}$), and rolling covariance/correlation across rolling windows ($W$). Values prior to $W$ observations return `null` to respect the warm-up period.
- **Inner Date Alignment**: All multi-asset analytics enforce strict calendar-date intersection matching. Non-overlapping trading days, holidays, and missing dates are excluded before calculating returns.

---

## 6. Financial Methodology

AURELIUS adheres to rigorous financial modeling conventions:

1. **Provider Adjusted Prices vs. Total Return**:
   Adjusted close prices provided by Yahoo Finance account for stock splits and historical cash dividend distributions. AURELIUS utilizes `adj_close` for historical returns, volatility, and drawdowns. However, this is treated as *provider-adjusted historical price data* and is **not** represented as an exact investor total return. It does not model dividend reinvestment timing, transaction costs, taxes, or cash drag.
2. **Moving Averages on Unadjusted Close**:
   Moving averages (SMA 20, SMA 50, SMA 200, EMA 20) are calculated strictly on actual historical transaction prices (`close`). Calculating moving averages on dividend-adjusted prices distorts historical support and resistance levels.
3. **Calendar-Time CAGR**:
   Compound Annual Growth Rate uses calendar year fractional duration ($(\text{End Date} - \text{Start Date}) / 365.25$). For horizons shorter than one full calendar year ($< 365$ days), CAGR is withheld (`None`) to prevent misleading extrapolation of short-term volatility.
4. **Drawdown Calculation & Tie-Breaking**:
   Drawdowns are computed relative to running historical peaks. Maximum Drawdown (MDD) uses deterministic tie-breaking (first occurrence of maximum drop), tracking exact peak and trough dates.
5. **Small-Sample Guardrails**:
   Mathematical estimators strictly enforce degrees-of-freedom requirements. When samples are insufficient ($N < 2$ for variance, $N < 3$ for skewness, $N < 4$ for excess kurtosis), estimators gracefully return `None` rather than fabricating zero values or raising unhandled exceptions.

---

## 7. Data Sources

- **Market Data Feed**: Development market data is obtained via the unofficial Yahoo Finance API via `yfinance`.
- **Macro Benchmarks**: Index tickers (`^GSPC`, `^IXIC`, `^DJI`, `^RUT`, `^TNX`, `^VIX`) provide macro context.
- **Resilience**: Ingestion adapters validate payload integrity, normalize column casing, ensure chronological sorting, and detect missing or malformed bars.

---

## 8. Testing & Verification

AURELIUS enforces continuous verification across all tiers:

- **182 Passed Pytest Tests**: Complete test suite spanning unit, domain, service, API, and integration tests.
- **29 Passed M4 Regression Tests**: Preserving historical moving average, drawdown, volatility, and benchmark mathematical integrity.
- **Ruff Code Audit**: 100% compliance on linting (`ruff check`) and formatting (`ruff format --check`) across 97 Python files.
- **Frontend Production Build**: Zero-error compilation via TypeScript compiler (`tsc -b`) and Vite production bundler.
- **API Smoke Verification**: Active verification of all core endpoints (Health, Quotes, OHLCV, Historical Analysis, Single-Ticker Quantitative, Multi-Ticker Correlation).

---

## 9. Milestone Roadmap

| Milestone | Title | Status | Commit / Tag |
|---|---|---|---|
| **M0** | Architecture & Project Foundation | ✅ Complete | `b18309e` (`milestone-0`) |
| **M1** | Market Data Infrastructure | ✅ Complete | `c8208ea` (`milestone-1`) |
| **M2** | Security Search & Company Profiles | ✅ Complete | `6c921fe` (`milestone-2`) |
| **M3** | Market Overview | ✅ Complete | `12b91f9` (`milestone-3`) |
| **M4** | Historical Market Analysis | ✅ Complete | `7c15d80` (`milestone-4`) |
| **M4.1**| Historical UI Stabilization | ✅ Complete | `cb601d3` |
| **M5** | Quantitative Analytics Foundation | ✅ Complete | `b6e2d9f` (`milestone-5`) |
| **M6** | Financial Statement Infrastructure | ⏳ Planned | — |
| **M7** | Financial Ratio & Valuation Engine | ⏳ Planned | — |
| **M8** | Factor Research & Asset Pricing | ⏳ Planned | — |
| **M9** | Portfolio Optimization & Risk Engine | ⏳ Planned | — |

---

## 10. Project Status

- **Current State**: Milestone 5 locked and verified.
- **Active Branch**: `main`.
- **Working Tree**: Clean.
- **Milestone Tags**: `milestone-4` (`7c15d80`), `milestone-5` (`b6e2d9f`).

---

## 11. Limitations

1. **Development Data Feed**: Market data is sourced from an unofficial Yahoo Finance feed. Quotes and prices may be delayed by 15 minutes or more and are subject to rate limiting and provider availability.
2. **Provider Adjustments**: Adjusted close data represents third-party backward adjustments and is not an exact model of investor total return.
3. **Security Classifications**: Sector and industry categorizations reflect data provider heuristics and do not represent authoritative GICS or BICS classifications.
4. **No Order Execution**: AURELIUS contains no trade execution, order routing, broker integration, or portfolio management account connectivity.
5. **Educational Scope**: AURELIUS is built strictly for educational, research, and portfolio demonstration purposes.

---

## 12. Future Work

- **Milestone 6**: Financial Statement Infrastructure (Balance Sheets, Income Statements, Cash Flow Statements, period normalization, restatement handling).
- **Milestone 7**: Ratio Analysis & Valuation Models (multiples, DCF models, WACC calculation).
- **Milestone 8**: Multi-Factor Risk Modeling (Fama-French 3-factor and 5-factor regression analysis).
- **Milestone 9**: Portfolio Construction (Markowitz Mean-Variance optimization, Black-Litterman allocation, Value at Risk / CVaR simulation).

---

## 13. Local Development

### Prerequisites
- **Python**: 3.12 or higher
- **Node.js**: 18 or higher (LTS recommended)
- **uv**: Modern Python package manager ([install uv](https://docs.astral.sh/uv/))

### Quick Start (Automated)
```bash
# Clone the repository
git clone https://github.com/Awwiiiii/aurelius-terminal.git
cd aurelius-terminal

# Run automated setup script
bash scripts/setup.sh
```

### Manual Setup

1. **Environment Configuration**:
   ```bash
   cp .env.example .env
   ```

2. **Backend Setup**:
   ```bash
   cd backend
   uv sync --dev
   uv run uvicorn aurelius.api.main:app --reload --port 8001
   ```

3. **Frontend Setup** (in a separate terminal):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Verify Application**:
   - Terminal Web Interface: `http://localhost:5173`
   - Interactive OpenAPI Docs: `http://localhost:8001/docs`
   - API Health Check: `http://localhost:8001/api/v1/health`

### Running Tests & Quality Checks

```bash
# Run backend pytest suite (182 tests)
cd backend
uv run pytest

# Run M4 regression suite
uv run pytest tests/unit/api/test_historical_endpoints.py tests/unit/domain/analytics/ tests/unit/services/test_historical_analysis_service.py

# Run Ruff linter and formatter check
uv run ruff check .
uv run ruff format --check .

# Run frontend build and typecheck
cd ../frontend
npm run build
```

---

## 14. Disclaimer

AURELIUS is an educational and portfolio financial intelligence project created for software engineering, financial modeling, and quantitative methodology research.

**Nothing contained in this software, documentation, or codebase constitutes financial, investment, legal, or tax advice.** AURELIUS is not a registered investment advisor, broker-dealer, or financial intermediary. Financial market data and analytics provided by this terminal are not guaranteed to be timely, complete, or accurate, and should never be used as the basis for making real-world financial investments or capital allocations. Past performance is no guarantee of future results.

AURELIUS is an independent open-source implementation and is not affiliated, associated, authorized, endorsed by, or in any way officially connected with Bloomberg L.P., FactSet Research Systems, S&P Global, London Stock Exchange Group (Refinitiv / LSEG), or Yahoo! Inc.
