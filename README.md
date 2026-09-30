# AURELIUS — Financial Research Terminal

AURELIUS is an educational and portfolio quantitative research terminal inspired by the analytical workflows of professional financial research platforms. It is an entirely independent, clean-room implementation demonstrating rigorous financial software engineering, domain-driven architecture, provenance-aware analytics, and modern full-stack web development.

AURELIUS does not reproduce, incorporate, or interface with proprietary Bloomberg, Capital IQ, Refinitiv, or other commercial platforms, systems, interfaces, or data feeds.

---

## Status

| Tier | State |
|---|---|
| Latest completed milestone | Milestone 7 (Fundamental Analysis) — Complete 🔒 |
| Backend test suite (latest verified run) | **384 passed**, 2 warnings |
| Ruff check | ✅ Clean |
| Ruff format --check | ✅ Clean |
| mypy (affected scope) | ✅ Clean |
| M7B.3 Phase 2 committed / tagged / pushed | ✅ Complete (`milestone-7b.3-phase2` / `d927116` on `origin/main`) |

> Milestone 7 (Fundamental Analysis) is complete. M7B.3 Phase 2 (Application Services, APIs & Temporal Market-Cap Resolution) has been implemented, verified, committed (`d927116e5378709dc0dfcb2218a5ac0eea48d95e`), tagged (`milestone-7b.3-phase2`), and pushed to `origin/main`.

---

## 1. Overview

AURELIUS is developed under a strict engineering philosophy:

> **CORRECTNESS > COMPLETENESS > SPEED**

Modern financial software requires uncompromising mathematical integrity, defensive validation, and clean domain boundaries. In AURELIUS:

- Every financial formula is documented in dedicated reference handbooks before implementation.
- Every statistical estimator explicitly declares its sample vs. population conventions, Bessel's corrections, and degrees-of-freedom guardrails.
- Financial data engineering distinguishes between raw transaction prices and retroactive provider adjustments.
- Methodology is auditable: pure domain analytics are isolated from infrastructure, provider adapters, and transport concerns.
- Market-cap observations carry explicit temporal provenance; historical periods cannot silently consume current market data.

---

## 2. What AURELIUS Does

AURELIUS is a multi-module financial research terminal spanning market data ingestion, quantitative analytics, and fundamental financial analysis:

- **Market intelligence**: real-time quotes, OHLCV history, candlestick charting, company profiles, and market-overview dashboards.
- **Historical analytics**: multi-horizon return attribution, drawdown analysis, moving averages, benchmark comparison, and rolling volatility.
- **Quantitative analytics**: descriptive statistics, distribution analysis, correlation matrices, beta, and rolling dynamics for single and multi-asset baskets.
- **Fundamental analysis**: financial statement ingestion and normalization, annual/quarterly/TTM computation, growth, profitability, liquidity, leverage, efficiency, cash-flow analysis, DuPont decomposition, common-size analysis, earnings-quality diagnostics, capital allocation, FCFF/FCFE, reinvestment and fundamental growth drivers, enterprise-value bridge, capital structure, Piotroski F-Score methodology, and Altman Z-Score methodology — all with strict period semantics and provenance-aware market-cap resolution.

---

## 3. Current Capabilities

### M0 — Architecture & Project Foundation
- **Layered clean architecture**: strict separation of Domain, Application Services, Provider Adapters, API Transport, and UI.
- **Domain error hierarchy**: structured exceptions (`AureliusError`, `NotFoundError`, `ProviderError`, `DataAlignmentError`, `InsufficientDataError`) mapped deterministically to HTTP status codes and structured client error responses.
- **Type-safe configuration**: centralized settings management via `pydantic-settings` reading from `.env` and environment variables.

### M1 — Market Data Infrastructure
- **OHLCV data engine**: daily bar models with chronological ordering and strict price validation (`high >= low`, `high >= open`, `high >= close`, `volume >= 0`).
- **Provider normalization**: resilient adapter for Yahoo Finance (`yfinance`) with payload normalization and error recovery.
- **Real-time snapshot quotes**: last price, bid, ask, change, percentage change, and volume metrics.
- **Interactive charting**: canvas-based candlestick charting with TradingView Lightweight Charts.

### M2 — Security Search & Company Profiles
- **Multi-asset ticker search**: real-time ticker search with input debouncing and symbol normalization.
- **Corporate profiles**: sector, industry, corporate officers, business descriptions, exchange listings, share counts, and capitalization statistics.

### M3 — Market Overview
- **Macro benchmark dashboard**: real-time monitoring of major equity benchmarks (`^GSPC`, `^IXIC`, `^DJI`, `^RUT`), 10-Year Treasury Yield (`^TNX`), and the Cboe Volatility Index (`^VIX`).
- **Market movers**: automated tracking of top gainers, top losers, and most active securities.
- **Sector monitoring**: visual sector performance tracking and market breadth metrics.

### M4 & M4.1 — Historical Market Analysis
- **Multi-horizon analysis**: flexible evaluation across `1M`, `3M`, `6M`, `1Y`, `5Y`, `Max` horizons.
- **Moving averages on raw close**: SMA 20, SMA 50, SMA 200, and EMA 20 computed strictly on actual transaction close prices to preserve historical support/resistance levels.
- **Drawdown & peak analytics**: running peak tracking, current drawdown, maximum drawdown (MDD) with deterministic tie-breaking, and peak/trough calendar date localization.
- **CAGR**: calendar-time compound annual growth rate, withheld for sub-year horizons to prevent misleading extrapolation.
- **Benchmark comparison**: relative normalized performance against S&P 500 (`^GSPC`) over a synchronized common base date.

### M5 — Quantitative Analytics Foundation
- **Single-ticker statistical profile**: complete univariate descriptive statistics, percentile distributions, and tail risk metrics.
- **Multi-ticker cross-asset analysis**: pairwise covariance and Pearson correlation matrices across configurable multi-asset baskets.
- **Deterministic distribution engine**: frequency histogram binning using Freedman-Diaconis adaptive sizing with zero data fabrication.
- **Rolling dynamics**: configurable rolling-window statistics with zero-indexed warm-up periods.
- **Strict data alignment**: calendar-date inner-join alignment across disparate security trading calendars.

### M6 — Financial Statement Infrastructure
- Financial statement ingestion, period normalization, and fiscal-calendar semantics.
- Structured financial period entities with annual, quarterly, and TTM classifications.
- Financial concept/fact taxonomy with provenance and diagnostic metadata.

### M7A — Fundamental Analysis Foundation
- Fundamental analysis entity layer, period registry, and base computation framework.
- Foundation for all downstream ratio, valuation, and diagnostic engines.

### M7B.1 — TTM Engine
- Trailing-twelve-month (TTM) computation from quarterly financial data.
- Strict period boundary semantics and fiscal-calendar alignment.

### M7B.2 — Advanced Fundamental Analysis Engine & Workspace
- **Growth analysis**: revenue, earnings, and cash-flow growth rates.
- **Profitability**: gross margin, operating margin, net margin, EBITDA margin, return on equity (ROE), return on assets (ROA), return on invested capital (ROIC).
- **Liquidity**: current ratio, quick ratio, cash ratio.
- **Leverage**: debt-to-equity, debt-to-assets, interest coverage, net debt.
- **Efficiency**: asset turnover, inventory turnover, receivables turnover, days outstanding metrics.
- **DuPont analysis**: three-factor and five-factor decomposition.
- **Common-size analysis**: income statement and balance sheet normalization.
- **Trend analysis**: directional trend detection across financial metrics.
- **Earnings-quality diagnostics**: accrual detection and quality scoring.
- Dedicated frontend fundamental analysis workspace with structured display.

### M7B.3 — Capital Allocation, Cash Flow & Credit

**Phase 1 — Capital Allocation, Cash Flow & Credit Domain Engines** (`milestone-7b.3-phase1` — ✅ Complete & Tagged):
- **Operating net working capital (NWC) & ΔNWC**: strict balance-sheet-driven computation.
- **Free cash flow to the firm (FCFF)** and **free cash flow to equity (FCFE)**: multi-path derivation with explicit input sourcing.
- **Reinvestment rate and fundamental growth drivers**: reinvestment-driven organic growth estimation.
- **Enterprise-value bridge**: equity → enterprise-value decomposition with net-debt adjustment.
- **Capital structure analysis**: debt/equity composition, net leverage, and capital-mix metrics.
- **Piotroski F-Score methodology**: nine-signal scoring framework across profitability, leverage, and operating efficiency signals.
- **Altman Z-Score methodology**: classic five-factor distress-prediction model (public-company formulation).

**Phase 2 — Application Services, APIs & Temporal Market-Cap Resolution** (`milestone-7b.3-phase2` — ✅ Complete 🔒):
- `MarketCapObservation` canonical value object carrying `value`, `as_of_date`, `currency`, and `source`.
- `MarketCapResolver` centralizing all market-cap resolution through strict temporal provenance.
- Application services and REST API endpoints exposing capital allocation, cash-flow, and credit domain results.
- Operations layer organizing service orchestration.

---

## 4. Architecture

AURELIUS follows Domain-Driven Design (DDD) principles with unidirectional dependencies:

```
backend/
└── aurelius/
    ├── api/                  # FastAPI REST endpoints & Pydantic response schemas
    ├── domain/               # Pure domain layer — no I/O, no framework dependencies
    │   ├── analytics/        # Returns, statistics, quantiles, distributions, multivariate, rolling
    │   ├── entities/         # Market, company, historical, quantitative & financial entities
    │   └── fundamental/      # Financial-domain engines (growth, profitability, liquidity,
    │                         #   leverage, efficiency, DuPont, cash flow, credit, capital allocation)
    ├── infrastructure/       # Logging, caching, and telemetry primitives
    ├── providers/            # External provider adapters (Yahoo Finance / yfinance)
    ├── services/             # Application orchestrators + operations layer
    │   └── operations/       # Fine-grained service operations
    └── settings.py           # Pydantic-settings configuration loader

frontend/
└── src/
    ├── api/                  # Typed API client contracts
    ├── components/           # Specialized workspace UI components
    │   ├── historical/       # Historical charts, moving averages, drawdown panels
    │   ├── quantitative/     # Quant workbench, statistics tables, histogram, correlation matrix
    │   └── fundamentals/     # Fundamental analysis workspace
    ├── pages/                # Terminal views
    └── index.css             # Monochromatic institutional dark-mode design system

docs/
├── architecture/             # Architecture decision records & milestone design documents
└── finance/                  # Finance handbook: methodology, conventions, formula references
```

### Key Architectural Boundaries

| Layer | Responsibility |
|---|---|
| **Pure domain analytics** (`domain/analytics/`) | Stateless mathematical functions on primitive sequences; zero I/O, zero framework dependencies |
| **Financial-domain engines** (`domain/fundamental/`) | Financial ratio, cash-flow, and credit engines operating on typed domain entities |
| **Provider adapters** (`providers/`) | Third-party API encapsulation; schema changes are absorbed here and never propagate inward |
| **Application services / operations** (`services/`) | Async orchestration, caching, data alignment, and computational dispatch |
| **API transport** (`api/`) | OpenAPI input validation and output schema serialization via Pydantic v2 |
| **React/TypeScript frontend** (`frontend/`) | Typed UI components and workspace views consuming the REST API |

Detailed architecture decisions and design rationale are documented in [`docs/architecture/`](docs/architecture/).

---

## 5. Financial & Quantitative Methodology

AURELIUS adheres to documented, auditable conventions throughout. Methodology highlights:

- **Return calculations**: simple return, log return, and cumulative compounded return; explicit distinction between provider-adjusted prices and investor total return.
- **Statistical estimators**: sample vs. population variance and standard deviation with explicit Bessel's correction; Fisher-Pearson skewness and excess kurtosis with strict small-sample guards (*N* >= 3 / *N* >= 4).
- **Distribution engine**: Freedman-Diaconis adaptive bin-width sizing; Hyndman-Fan Method 7 percentile interpolation.
- **Multivariate analytics**: sample covariance, Pearson correlation, market beta, and tracking error with calendar-date inner-join alignment.
- **Moving averages**: computed on unadjusted transaction close prices to preserve historical technical levels.
- **CAGR**: withheld for horizons shorter than one calendar year.
- **Drawdown**: running-peak relative; MDD with deterministic first-occurrence tie-breaking.
- **Fundamental ratios**: profitability, liquidity, leverage, efficiency, growth, and DuPont — all computed from typed financial period entities with explicit period boundaries.
- **TTM semantics**: strict trailing-twelve-month summation/averaging with fiscal-calendar alignment.
- **Earnings quality**: accrual detection and quality-scoring diagnostics.
- **FCFF / FCFE**: multi-path derivation with explicit input sourcing.
- **Piotroski F-Score**: nine-signal framework across profitability, leverage/source-of-funds, and operating efficiency signals.
- **Altman Z-Score**: five-factor public-company distress model.

Full formula derivations, conventions, and guardrail specifications are documented in [`docs/finance/`](docs/finance/).

---

## 6. Data & Provenance

### Market Data
- **Source**: unofficial Yahoo Finance API via `yfinance`.
- **Quotes may be delayed** by 15 minutes or more; treat all market data as potentially delayed.
- **Ingestion**: provider adapters validate payload integrity, normalize column casing, ensure chronological ordering, and detect missing or malformed bars.

### Financial Statements
- Financial period entities carry explicit fiscal-period boundaries, period type (annual / quarterly / TTM), and source provenance.

### Market-Cap Temporal Provenance

AURELIUS introduced a canonical `MarketCapObservation` value object containing:

| Field | Description |
|---|---|
| `value` | Market capitalization amount |
| `as_of_date` | Explicit observation date |
| `currency` | Currency denomination |
| `source` | Data source identifier |

Market-cap resolution is centralized through `MarketCapResolver`. A market-cap observation is considered temporally compatible with a financial period **only when**:

```
D_obs == D_fin
```

where `D_obs` is the explicit market-cap observation date and `D_fin` is the financial period cutoff date.

- Missing `as_of_date` metadata is treated as **unavailable** — not estimated or inferred.
- Historical financial periods **cannot** consume today's or any current market capitalization.
- There is no fuzzy date matching or tolerance window.

This design ensures that enterprise-value computations, EV/EBITDA multiples, and price-to-book ratios derived from historical periods are temporally coherent with the financial data they accompany.

---

## 7. Verification & Quality

AURELIUS enforces continuous verification across all tiers:

- **Backend test suite**: **384 passed**, 2 warnings (latest verified run). Spans unit, domain, service, API, and integration tests.
- **No Phase 1 domain engines or tests were modified** during Phase 2 implementation; mathematical integrity of M7B.3 Phase 1 engines is preserved.
- **Ruff**: 100% compliance on linting (`ruff check`) and formatting (`ruff format --check`).
- **mypy**: passes for all affected source and test scope.
- **Frontend**: zero-error compilation via TypeScript compiler (`tsc -b`) and Vite production bundler.

---

## 8. Technology Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.12 |
| **Package management** | uv |
| **API framework** | FastAPI |
| **Schema validation** | Pydantic v2 |
| **HTTP client** | HTTPX |
| **Data processing** | pandas |
| **Market data adapter** | yfinance |
| **Frontend framework** | React + TypeScript |
| **Build tool** | Vite |
| **Styling** | Vanilla CSS (institutional dark-mode design system) |
| **Financial charting** | TradingView Lightweight Charts |
| **Test runner** | pytest, pytest-asyncio |
| **Linting & formatting** | Ruff |
| **Type checking (backend)** | mypy |
| **Type checking (frontend)** | tsc |

---

## 9. Milestone Roadmap

| Milestone | Title | Status | Tag / Commit |
|---|---|---|---|
| **M0** | Architecture & Project Foundation | ✅ Complete 🔒 | `milestone-0` (`b18309e`) |
| **M1** | Market Data Infrastructure | ✅ Complete 🔒 | `milestone-1` (`c8208ea`) |
| **M2** | Security Search & Company Profiles | ✅ Complete 🔒 | `milestone-2` (`6c921fe`) |
| **M3** | Market Overview | ✅ Complete 🔒 | `milestone-3` (`12b91f9`) |
| **M4** | Historical Market Analysis | ✅ Complete 🔒 | `milestone-4` (`7c15d80`) |
| **M4.1** | Historical UI Stabilization | ✅ Complete 🔒 | `cb601d3` |
| **M5** | Quantitative Analytics Foundation | ✅ Complete 🔒 | `milestone-5` (`b6e2d9f`) |
| **M6** | Financial Statement Infrastructure | ✅ Complete 🔒 | `milestone-6` (`de67fa4`) |
| **M7A** | Fundamental Analysis Foundation | ✅ Complete 🔒 | `milestone-7a` (`521e12a`) |
| **M7B.1** | TTM Engine | ✅ Complete 🔒 | `milestone-7b.1` (`a71923f`) |
| **M7B.2** | Advanced Fundamental Analysis Engine & Workspace | ✅ Complete 🔒 | `milestone-7b.2-phase4` (`2e92878`) |
| **M7B.3 Ph.1** | Capital Allocation, Cash Flow & Credit Domain Engines | ✅ Complete 🔒 | `milestone-7b.3-phase1` (`8365188`) |
| **M7B.3 Ph.2** | Application Services, APIs & Temporal Market-Cap Resolution | ✅ Complete 🔒 | `milestone-7b.3-phase2` (`d927116`) |
| **M8** | Valuation Engine | ⏳ Planned | — |
| **M9** | Peer Comparison | ⏳ Planned | — |
| **M10** | Financial Screener | ⏳ Planned | — |
| **M11** | Portfolio Analytics | ⏳ Planned | — |
| **M12** | Risk Engine | ⏳ Planned | — |
| **M13** | Quant Research Workspace | ⏳ Planned | — |
| **M14** | Backtesting Engine | ⏳ Planned | — |
| **M15** | Factor Research | ⏳ Planned | — |
| **M16** | Options & Derivatives | ⏳ Planned | — |
| **M17** | Advanced Quantitative Research | ⏳ Planned | — |
| **M18** | Institutional-Style Research Platform | ⏳ Planned | — |

---

## 10. Limitations

1. **Development data feed**: market data is sourced from an unofficial Yahoo Finance feed. Quotes and prices may be delayed by 15 minutes or more and are subject to rate limiting and provider availability.
2. **Provider adjustments**: adjusted close data represents third-party backward adjustments and is not an exact model of investor total return. It does not model dividend reinvestment timing, transaction costs, taxes, or cash drag.
3. **Security classifications**: sector and industry categorizations reflect data provider heuristics and do not represent authoritative GICS or BICS classifications.
4. **No order execution**: AURELIUS contains no trade execution, order routing, broker integration, or portfolio account connectivity.
5. **Educational scope**: AURELIUS is built strictly for educational, research, and portfolio demonstration purposes. It is not a production financial service.

---

## 11. Local Development

### Prerequisites
- **Python** 3.12 or higher
- **Node.js** 18 or higher (LTS recommended)
- **uv** — modern Python package manager ([install uv](https://docs.astral.sh/uv/))

### Quick Start (Automated)
```bash
# Clone the repository
git clone https://github.com/Awwiiiii/aurelius-terminal.git
cd aurelius-terminal

# Run automated setup script
bash scripts/setup.sh
```

### Manual Setup

1. **Environment configuration**:
   ```bash
   cp .env.example .env
   ```

2. **Backend setup**:
   ```bash
   cd backend
   uv sync --dev
   uv run uvicorn aurelius.api.main:app --reload --port 8001
   ```

3. **Frontend setup** (separate terminal):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Verify application**:
   - Terminal Web Interface: `http://localhost:5173`
   - Interactive OpenAPI Docs: `http://localhost:8001/docs`
   - API Health Check: `http://localhost:8001/api/v1/health`

### Running Tests & Quality Checks

```bash
# Run full backend pytest suite
cd backend
uv run pytest

# Run Ruff linter and formatter check
uv run ruff check .
uv run ruff format --check .

# Run frontend typecheck and build
cd ../frontend
npm run build
```

---

## 12. Future Direction

The planned roadmap builds on the established fundamental analysis infrastructure toward a full-spectrum quantitative research environment:

- **M8 — Valuation Engine**: intrinsic valuation models (DCF, DDM), earnings-based multiples, and EV-based multiples using period-aligned market-cap provenance.
- **M9 — Peer Comparison**: cross-sectional peer ranking and relative valuation across sectors and industries.
- **M10 — Financial Screener**: multi-criteria fundamental and quantitative screening across the investable universe.
- **M11 — Portfolio Analytics**: holdings-level attribution, performance decomposition, and exposure analysis.
- **M12 — Risk Engine**: factor-based risk decomposition, Value at Risk (VaR), and Conditional Value at Risk (CVaR).
- **M13 — Quant Research Workspace**: interactive quantitative research environment with scriptable analysis.
- **M14 — Backtesting Engine**: strategy simulation and historical performance evaluation.
- **M15 — Factor Research**: systematic factor construction, signal analysis, and Fama-French model regression.
- **M16 — Options & Derivatives**: options pricing, Greeks computation, and derivatives analytics.
- **M17 — Advanced Quantitative Research**: advanced statistical modeling and multi-factor portfolio construction.
- **M18 — Institutional-Style Research Platform**: integrated research publishing, scenario analysis, and presentation tooling.

---

## 13. Disclaimer

AURELIUS is an educational and portfolio financial intelligence project created for software engineering, financial modeling, and quantitative methodology research.

**Nothing contained in this software, documentation, or codebase constitutes financial, investment, legal, or tax advice.** AURELIUS is not a registered investment advisor, broker-dealer, or financial intermediary. Financial market data and analytics provided by this terminal are not guaranteed to be timely, complete, or accurate, and should never be used as the basis for making real-world financial investments or capital allocations. Past performance is no guarantee of future results.

AURELIUS is an independent open-source implementation and is not affiliated, associated, authorized, endorsed by, or in any way officially connected with Bloomberg L.P., FactSet Research Systems, S&P Global, London Stock Exchange Group (Refinitiv / LSEG), or Yahoo! Inc.
