# AURELIUS — Financial Intelligence & Research Terminal

A professional-grade financial intelligence and quantitative research terminal.

AURELIUS is designed as a serious financial research platform demonstrating:
financial data engineering, market data analysis, fundamental analysis, valuation,
portfolio analytics, risk analysis, quantitative research, and backtesting.

> **Status**: Milestone 4 — Historical Market Analysis
 
---

## Project Structure

```
aurelius/
├── backend/          # Python 3.12 backend (FastAPI + uv)
├── frontend/         # React 18 + TypeScript + Vite frontend
├── docs/
│   ├── architecture/ # Architecture overview and decision records
│   └── finance/      # Finance handbook (concepts, formulas, assumptions)
└── scripts/          # Developer utility scripts
```

## Quick Start

```bash
# One-command setup
bash scripts/setup.sh
```

See `scripts/setup.sh` for what the setup does step by step.

## Development

**Backend**
```bash
cd backend
source .venv/bin/activate
uvicorn aurelius.api.main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm run dev
```

The frontend dev server runs at `http://localhost:5173`.
The backend API is at `http://localhost:8000`.
API documentation (auto-generated): `http://localhost:8000/docs`

## Environment Setup

```bash
cp .env.example .env
# Edit .env with your API keys
```

## Architecture

See [`docs/architecture/00-overview.md`](docs/architecture/00-overview.md) for the
full architecture description.

## Finance Handbook

See [`docs/finance/`](docs/finance/) for the financial concepts handbook.
This is a living reference document that explains every financial concept, formula,
and assumption used in the implementation:
- [`01-market-basics.md`](docs/finance/01-market-basics.md) — Market microstructure & orders
- [`02-returns.md`](docs/finance/02-returns.md) — Total return & return calculations
- [`03-market-data.md`](docs/finance/03-market-data.md) — Market data infrastructure & adjustments
- [`04-security-and-company-data.md`](docs/finance/04-security-and-company-data.md) — Security identity, listings, & classifications
- [`05-market-benchmarks-and-indicators.md`](docs/finance/05-market-benchmarks-and-indicators.md) — Market benchmarks, volatility, and telemetry
- [`06-historical-market-analysis.md`](docs/finance/06-historical-market-analysis.md) — Historical market analysis, drawdowns, CAGR, and volatility

## Development Philosophy

> CORRECTNESS > COMPLETENESS > SPEED

AURELIUS is developed incrementally using a milestone system. Each milestone is reviewed
before the next begins. Every financial formula is documented, tested, and verified.

## Milestone Roadmap

| Milestone | Name | Status |
|---|---|---|
| 0 | Architecture & Project Foundation | ✅ Complete |
| 1 | Market Data Infrastructure | ✅ Complete |
| 2 | Security Search & Company Profiles | ✅ Complete |
| 3 | Market Overview | ✅ Complete |
| 4 | Historical Market Analysis | 🟡 Implemented (Awaiting Review) |
| 5 | Quantitative Analytics Foundation | ⏳ Pending |
| 6 | Financial Statement Infrastructure | ⏳ Pending |
| 7–18 | Further milestones | ⏳ Pending |

## Technology Stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.12 |
| Package manager | uv |
| API framework | FastAPI |
| Data validation | Pydantic v2 |
| HTTP client | httpx |
| Frontend framework | React 18 + TypeScript |
| Frontend build | Vite |
| Financial charting | TradingView Lightweight Charts (Milestone 1+) |
| Database | SQLite (development) → PostgreSQL (production path) |
| Testing | pytest, pytest-asyncio |
| Linting | ruff |
| Type checking | mypy |

## License

Private — not licensed for redistribution.
