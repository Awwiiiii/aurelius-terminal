# 04 — Security Identity, Corporate Entity Intelligence, and Market Classifications

## 1. Conceptual Distinction: Company vs. Security vs. Listing vs. Ticker

In institutional financial architecture, collapsing corporate business entities, tradable financial assets, and exchange quotation venues into a single flat "ticker" string creates fatal architectural limitations. AURELIUS establishes a strict conceptual taxonomy:

```
┌───────────────────────────────────────────────────────────┐
│                    COMPANY (Entity)                       │
│  Apple Inc. (Corporate Issuer, HQ, Executives, Financials)│
└─────────────────────────────┬─────────────────────────────┘
                              │ issues
                              ▼
┌───────────────────────────────────────────────────────────┐
│                   SECURITY (Instrument)                   │
│  Apple Inc. Common Stock (Tradable Financial Instrument)   │
└─────────────────────────────┬─────────────────────────────┘
                              │ listed on
                              ▼
┌───────────────────────────────────────────────────────────┐
│                     LISTING (Venue)                       │
│  NASDAQ (AAPL:USD)      XETRA (APC:EUR)     LSE (0R2V:USD)│
└───────────────────────────────────────────────────────────┘
```

1. **Company (`CompanyProfile`)**:
   - The legal corporate business enterprise (e.g., Apple Inc., Microsoft Corporation).
   - Holds operating attributes: headquarters, description, corporate officers, employee count, and financial statements.
   - **Non-Corporate Exception**: Mutual funds, ETFs (e.g., SPY), indices (e.g., ^GSPC), and commodity contracts are financial instruments, but they are **not operating business companies**.

2. **Security (`Security`)**:
   - The tradable financial contract or asset class (e.g., Common Stock, Preferred Class A, ETF Share, Future, Option).
   - In institutional master systems, reconciled via permanent global identifiers (CUSIP, ISIN, FIGI, SEDOL).
   - In Milestone 2, `Security` holds instrument classification (`AssetType`) and carries provider listing context (`ticker`, `exchange`, `currency`, `timezone`). It is documented so a future dedicated multi-venue `Listing` model can be introduced without rework of `CompanyProfile` or `Security`.

3. **Listing & Ticker**:
   - The venue-specific trading quote convention on a particular stock exchange.
   - The same security can have multiple listings across multiple global exchanges (e.g. Apple traded in New York as `AAPL` in USD, in Frankfurt as `APC` in EUR).
   - A ticker is merely a transient routing symbol assigned by an exchange, subject to changes, corporate spinoffs, or reassignments.

---

## 2. Provider Sector & Industry Classifications vs. Authoritative GICS

Financial data APIs routinely report `sector` and `industry` strings. In AURELIUS, these fields are explicitly documented as **"Yahoo Finance provider-supplied sector/industry classifications"** and must **never** be mischaracterized as authoritative GICS:

1. **What is GICS?**:
   - The **Global Industry Classification Standard (GICS)** is an authoritative, proprietary, four-tiered financial taxonomy developed and administered jointly by **MSCI** and **S&P Dow Jones Indices**.
   - GICS comprises 11 Sectors, 25 Industry Groups, 74 Industries, and 163 Sub-Industries, governed by strict methodology books and annual committee reviews.
   - GICS classification codes are copyrighted commercial intellectual property requiring licensing agreements directly from S&P/MSCI.

2. **Provider Classifications (Yahoo Finance / Unofficial Feeds)**:
   - Yahoo Finance derives sector/industry strings from internal mapping feeds (historically Refinitiv/Morningstar/ICE).
   - While frequently corresponding in name to major economic sectors, they do not provide canonical GICS 8-digit classification codes (`sub_industry_code`).
   - In AURELIUS, UI displays and documentation explicitly label these as provider-supplied classifications.

---

## 3. Polymorphic Instruments: Corporate Equities vs. ETFs & Indices

A major data-quality bug in naive terminals is treating non-corporate instruments as "missing company" errors:

1. **Exchange-Traded Funds (ETFs) — e.g. `SPY`, `QQQ`, `VTI`**:
   - An ETF is a pooled investment fund traded on an exchange, holding a basket of stocks, bonds, or commodities.
   - An ETF does not have an operating headquarters, corporate officers, or employee headcount.
   - Treating `SPY` as an error or throwing a `404 Not Found` because its corporate profile is absent violates financial reality.
   - AURELIUS returns `200 OK` with `company_profile = null` and `is_operating_company = false`, displaying a dedicated Instrument Overview card.

2. **Benchmark Indices — e.g. `^GSPC` (S&P 500), `^DJI` (Dow Jones), `^IXIC` (Nasdaq Composite)**:
   - An index is a mathematical statistical calculation tracking performance of a hypothetical basket of securities.
   - Indices are non-tradable benchmarks (though futures and ETFs derive from them).
   - In AURELIUS, indices are recognized under `AssetType.INDEX`, with null corporate profile and explicit benchmark categorization.

---

## 4. Strict Data Integrity: No Plausible Fabrication

Financial software must maintain absolute truthfulness regarding missing data:

- **Missing Currency**: Naive code often defaults missing currency to `"USD"`. This creates severe financial calculation errors if a foreign security (e.g. on the London, Tokyo, or Toronto exchange) has its price converted or aggregated as US dollars.
- **Invariant**: If a data feed omits currency or reports an unmapped currency, AURELIUS stores `Currency.UNKNOWN` or `None`. It **never** defaults to `USD`.
- **Missing Corporate Fields**: Unknown employee counts or missing addresses remain `None`, rendered as `—` in the UI rather than fabricated defaults.

---

## 5. Ticker Symbology & Grammar

AURELIUS ticker validation regex `^[A-Z0-9.\-=^]{1,12}$` permits standard exchange symbology:

- **Indices (`^`)**: Yahoo Finance prefixes index symbols with a caret (`^GSPC`, `^DJI`, `^IXIC`, `^VIX`) to distinguish them from equity ticker namespaces.
- **Continuous Futures (`=`)**: Commodity and financial futures use `=F` suffix notation (`ES=F` for S&P E-mini, `NQ=F` for Nasdaq 100 E-mini, `CL=F` for Crude Oil).
- **Share Classes & Foreign Venues (`.` and `-`)**: Dual-class equities utilize periods or hyphens (`BRK.B`, `BRK-B` for Berkshire Hathaway Class B; `BF.B` for Brown-Forman; `SHOP.TO` for TSX listings).
