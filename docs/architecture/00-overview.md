# AURELIUS — Architecture Overview

> This document is the starting point for understanding the AURELIUS system design.
> It describes the high-level architecture and points to more detailed documents.
> **Architecture Decision Records** (ADRs) live in `decisions/` and document why
> significant choices were made.

---

## System Overview

AURELIUS is a professional-grade financial intelligence and quantitative research terminal.
It runs locally as a client-server application:

```
Browser (React SPA)
        │  HTTP/JSON
        ▼
FastAPI Backend (Python 3.12)
        │
        ├─── Domain Layer (pure Python — no I/O)
        │
        ├─── Provider Abstraction (abstract interfaces)
        │         └── Concrete Providers (yfinance, FMP, EDGAR, ...)
        │
        └─── Infrastructure (httpx, SQLite/PostgreSQL, logging)
```

---

## Layer Responsibilities

### Presentation (Frontend)

- **Technology**: React 18 + TypeScript, built with Vite
- **Location**: `frontend/`
- **Responsibility**: Render data received from the API. No financial logic.
- **Rule**: The frontend must not perform financial calculations.
  All numerical results come from the backend.
- **Charting**: TradingView Lightweight Charts (added in Milestone 1)

### API Layer

- **Technology**: FastAPI
- **Location**: `backend/aurelius/api/`
- **Responsibility**: HTTP request handling, input validation (Pydantic), error mapping,
  CORS, provider injection via FastAPI's dependency injection system.
- **Rule**: The API layer must not perform financial calculations.
  It delegates to the domain layer.

### Domain Layer

- **Technology**: Pure Python 3.12 (dataclasses, Pydantic models)
- **Location**: `backend/aurelius/domain/`
- **Responsibility**: Financial entities, business rules, financial calculations.
- **Critical rule**: Zero dependency on FastAPI, SQLAlchemy, httpx, or any provider SDK.
  All domain code must be testable with `pytest` alone — no server, no network, no DB.

### Provider Abstraction

- **Location**: `backend/aurelius/providers/`
- **Responsibility**: Abstract interfaces for market data providers.
  Concrete providers implement the interface. The API layer receives providers via
  dependency injection and never references a concrete provider class directly.
- **Rule**: Adding or replacing a provider must not require changes to the domain layer
  or the API layer (except dependency injection bindings).

### Infrastructure

- **Location**: `backend/aurelius/infrastructure/`
- **Responsibility**: All I/O adapters — HTTP client (httpx), database adapters
  (SQLAlchemy sessions), structured logging configuration.
- **Rule**: Infrastructure never contains financial logic.

---

## Data Flow (Milestone 1 target example: "Get Quote for AAPL")

```
1. User types "AAPL" in frontend
2. Frontend sends: GET /api/v1/market/quote/AAPL
3. FastAPI validates ticker (Pydantic, pattern check)
4. FastAPI injects the configured MarketDataProvider
5. Provider.get_quote("AAPL") is called
6. Provider calls Yahoo Finance API via httpx
7. Raw response is validated for data quality
8. A Quote domain entity is returned
9. FastAPI serializes Quote to JSON
10. Frontend renders: $189.84 (+1.23%)
```

---

## Current State (Milestone 2)

| Component | Status |
|---|---|
| Git repository | ✅ Initialized |
| Backend scaffold | ✅ Created |
| Domain errors | ✅ Implemented (including InvalidSearchQueryError) |
| Domain entities (Quote, OHLCV, Security, CompanyProfile, SecuritySearchResult) | ✅ Implemented (M2) |
| Settings (pydantic-settings) | ✅ Implemented |
| FastAPI app + health endpoint | ✅ Implemented |
| Infrastructure logging | ✅ Implemented |
| Provider abstraction (MarketDataProvider, Registry) | ✅ Implemented (M2: search + profile) |
| YFinanceProvider (selective retry, thread offload) | ✅ Implemented (M2: search + profile) |
| Market data endpoints (`/quote`, `/ohlcv`) | ✅ Implemented (M1) |
| Search & profile endpoints (`/search`, `/security/{ticker}`, `/company/{ticker}`) | ✅ Implemented (M2) |
| Frontend UI (AppShell, SearchBar, SecurityHeader, CompanyProfileCard, QuoteCard, OHLCVTable) | ✅ Implemented (M2) |
| Database schema | 🔲 Milestone 3+ |
| Financial calculations | 🔲 Milestone 4+ |

---

## Key Design Decisions

### Why a Layered Monolith?

AURELIUS starts as a layered monolith (not microservices) because:
1. Single developer — distributed systems add operational overhead without benefit.
2. Financial calculations require tight coupling between domain concepts.
3. The internal layered structure can be extracted into services later if needed.

### Why SQLite → PostgreSQL (not just SQLite)?

SQLite is correct for local single-user development.
The PostgreSQL production path exists for future deployment capability.

**Important**: Migrating from SQLite to PostgreSQL is NOT a one-line connection string
change. It requires:
- Schema compatibility review (SQLite is less strict on types and constraints)
- Query review (SQL dialects differ in subtle ways)
- Index strategy review
- Testing the migration script with real data

### Why Provider Abstraction from Day 1?

Financial data providers are unreliable:
- They change APIs without notice
- They impose rate limits
- They are acquired, shut down, or change pricing
- Data quality varies across providers

Building provider abstraction from the start means switching providers requires
only implementing a new concrete class — no domain or API changes needed.

---

## Architecture Decision Records

Significant architectural decisions are documented in `decisions/`.

Format: `NNNN-title.md` (e.g., `0001-use-sqlite-for-development.md`)

An ADR is only created when documenting an **actual significant decision that was made**.
Do not create ADRs for trivial choices.

**Current ADRs**:
- [`decisions/0001-yfinance-as-primary-provider.md`](decisions/0001-yfinance-as-primary-provider.md) — YFinance as Primary Market Data Provider in Milestone 1
- [`decisions/0002-security-search-and-company-profile-architecture.md`](decisions/0002-security-search-and-company-profile-architecture.md) — Security Search, Identity Context, and Polymorphic Company Profile Architecture
- [`decisions/0003-market-overview-and-session-telemetry.md`](decisions/0003-market-overview-and-session-telemetry.md) — Market Overview Workspace, Canonical Benchmarks, and Indicative Session Telemetry

---

## Related Documents

- [`../finance/01-market-basics.md`](../finance/01-market-basics.md) — Financial concepts
- [`../finance/02-returns.md`](../finance/02-returns.md) — Return calculations
- [`../finance/03-market-data.md`](../finance/03-market-data.md) — Market data infrastructure
- [`../finance/04-security-and-company-data.md`](../finance/04-security-and-company-data.md) — Security identity & classifications
- [`../finance/05-market-benchmarks-and-indicators.md`](../finance/05-market-benchmarks-and-indicators.md) — Market benchmarks, volatility, and telemetry
- [Backend `pyproject.toml`](../../backend/pyproject.toml) — Dependency justifications
- [`.env.example`](../../.env.example) — Configuration reference

