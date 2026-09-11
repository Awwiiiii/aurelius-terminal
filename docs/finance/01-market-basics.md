# Finance Handbook — Chapter 1: Market Basics

> **Purpose**: This chapter is a reference for the developer building AURELIUS.
> It explains foundational market concepts precisely, with the level of rigor
> required to implement them correctly in code.

---

## 1.1 What Is a Security?

A **security** is a tradeable financial asset. The major categories relevant to AURELIUS:

| Type | Examples | Notes |
|---|---|---|
| **Equity (Stock)** | AAPL, MSFT, TSLA | Ownership stake in a corporation |
| **Exchange-Traded Fund (ETF)** | SPY, QQQ, VTI | Basket of securities, trades like a stock |
| **Index** | S&P 500, NASDAQ-100 | Theoretical benchmark; not directly tradeable |
| **Bond / Fixed Income** | US Treasury, Corporate Bond | Debt instrument; later milestones |
| **Option / Derivative** | AAPL Call, SPX Put | Derivatives; Milestone 16 |
| **Cryptocurrency** | BTC, ETH | Digital assets; not in initial scope |

**Important**: An index (e.g., S&P 500) is NOT directly tradeable.
You trade instruments that track it (SPY ETF, S&P 500 futures).
Do not confuse index performance with the performance of index-tracking products.

---

## 1.2 Identifiers

### Ticker Symbol

A **ticker** (or ticker symbol) is a short alphabetic code identifying a security on
a specific exchange.

Examples:
- `AAPL` — Apple Inc. on NASDAQ
- `AAPL.L` — Apple Inc. depositary receipt on London Stock Exchange (different instrument)
- `BRK.B` — Berkshire Hathaway Class B on NYSE

**Ticker reuse**: Tickers are NOT globally unique and NOT permanent.
- A ticker can be reassigned to a different company after a delisting.
- The same company may have different tickers on different exchanges.
- Companies change tickers after mergers, spinoffs, or rebranding.

**Consequence for AURELIUS**: Always store `(ticker, exchange)` together, not ticker alone.
When building historical databases, be aware that a ticker today may not refer to the
same company as that ticker ten years ago.

### ISIN, CUSIP, SEDOL

For professional-grade identification, securities use standardized identifiers:
- **ISIN**: International Securities Identification Number (12-character alphanumeric)
- **CUSIP**: Committee on Uniform Securities Identification Procedures (9-character, US/CA)
- **SEDOL**: Stock Exchange Daily Official List (7-character, UK/international)

AURELIUS uses ticker symbols for Milestones 0–5. ISINs/CUSIPs may be introduced
in Milestone 6+ when dealing with financial statement data from providers like EDGAR.

---

## 1.3 Exchanges

A **stock exchange** is an organized marketplace where securities are listed and traded.

| Exchange | Abbreviation | Country | Notes |
|---|---|---|---|
| New York Stock Exchange | NYSE | USA | Largest by market cap |
| NASDAQ | NASDAQ | USA | Tech-heavy listing |
| London Stock Exchange | LSE | UK | |
| Tokyo Stock Exchange | TSE | Japan | |
| Shanghai Stock Exchange | SSE | China | Restricted foreign access |
| Euronext | Euronext | EU | Multi-country |

**Trading hours matter for AURELIUS**:
- Prices only update during trading hours.
- Weekends and market holidays produce no OHLCV bars.
- Pre-market and after-hours trading exist but have lower liquidity and wider spreads.
- Different exchanges are in different timezones.

**Implementation note**: All timestamps in AURELIUS should be stored in UTC.
Display conversion to local time is a presentation concern.

---

## 1.4 OHLCV

**OHLCV** is the canonical representation of price activity over a time period:

| Field | Meaning |
|---|---|
| **O** — Open | Price of the first trade in the period |
| **H** — High | Highest price during the period |
| **L** — Low | Lowest price during the period |
| **C** — Close | Price of the last trade in the period |
| **V** — Volume | Total number of shares (or contracts) traded |

A single OHLCV bar is called a **candlestick** (in charting terminology) or a **bar**.

**Data quality constraints that must always hold**:
```
Low ≤ Open ≤ High
Low ≤ Close ≤ High
Low ≤ High  (trivially follows from above)
Volume ≥ 0
```

If any of these constraints are violated, the data is incorrect and should be flagged
as a `DataQualityError`. Do NOT silently accept an OHLCV bar where Low > High.

**Common intervals**:
- `1m`, `5m`, `15m`, `30m` — Intraday (minute-level)
- `1h` — Hourly
- `1d` — Daily (most common for fundamental analysis)
- `1wk` — Weekly
- `1mo` — Monthly

---

## 1.5 Raw Price vs. Adjusted Price

This is one of the most important distinctions in financial data engineering.

### Raw (Unadjusted) Close

The actual price at which the last trade occurred during the trading session.

### Adjusted Close

A retroactively modified price series that accounts for corporate actions, making
the historical series comparable across time.

### Corporate Actions That Trigger Adjustment

#### Stock Splits

A **stock split** increases the number of shares outstanding by dividing existing shares.
Example: 2-for-1 split — one share becomes two; price approximately halves.

Effect on raw price series:
```
Before split:   ... $180, $182, $180 | SPLIT | $90, $91, $92 ...
```

Effect on adjusted price series (backward-adjusted):
```
All pre-split prices are multiplied by 0.5:
... $90, $91, $90 | SPLIT | $90, $91, $92 ...
```

Without adjustment, computing a return across a split date produces a spurious −50% return.

#### Cash Dividends

When a company pays a **cash dividend**, the stock price typically drops by approximately
the dividend amount on the ex-dividend date (investors who sold before ex-date don't
receive the dividend).

Effect on raw price series: Apparent price drop on ex-dividend date.
Effect on adjusted close: Pre-dividend prices are scaled down by a factor.

### ⚠️ Critical Warning: Adjusted Price Methodology Is Provider-Specific

> There is **no universal standard** for how providers compute adjusted prices.
> The adjustment methodology depends on the provider.

Common differences between providers:
- Some providers adjust only for splits; some adjust for splits + dividends.
- Some use proportional adjustment (multiply by a factor); others use additive adjustment.
- Some apply forward adjustment (scale future prices); most use backward adjustment (scale
  historical prices).
- The adjustment factor may change retroactively when the provider revises historical data.

**Consequence**:
- Do NOT assume that `adj_close` from Yahoo Finance equals `adj_close` from another provider.
- Do NOT assume that `adj_close` always represents total return.
- ALWAYS document which provider's adjusted series you are using.
- NEVER mix unadjusted prices from one provider with adjusted prices from another.

### What Adjusted Close Approximates (With Caveats)

When `adj_close` accounts for both splits and dividends using backward proportional
adjustment, the return computed from it **approximates** the total return a buy-and-hold
investor would have earned, assuming dividends were reinvested at the ex-dividend price.

**It is an approximation, not the exact total return**, because:
- Transaction costs for reinvesting dividends are ignored.
- Fractional shares from dividend reinvestment are not modeled.
- The exact reinvestment price used in the adjustment may differ from actual prices.
- Tax effects are not considered.

### Domain Model Decision (Milestone 0)

The AURELIUS `OHLCV` entity (to be created in Milestone 1) will store:
- `close`: Raw close price
- `adj_close`: Provider-adjusted close (provider-specific methodology)
- `source`: Provider identifier
- `is_adjusted`: Boolean flag

A future `CorporateAction` domain entity will model splits, dividends, and other events
explicitly. This will allow AURELIUS to apply its own adjustment methodology in later
milestones, removing dependence on provider-specific adjustment logic.

---

## 1.6 Market Capitalization

**Market capitalization** (market cap) is the total market value of a company's
outstanding equity:

```
Market Cap = Share Price × Shares Outstanding
```

| Category | Approximate Range (USD) |
|---|---|
| Mega-cap | > $200B |
| Large-cap | $10B – $200B |
| Mid-cap | $2B – $10B |
| Small-cap | $300M – $2B |
| Micro-cap | $50M – $300M |
| Nano-cap | < $50M |

**Important distinctions**:
- Market Cap measures only the **equity value** — not the total value of the firm.
- Market Cap ≠ Enterprise Value (EV). EV also accounts for debt and cash.
  *(Enterprise Value = Market Cap + Total Debt − Cash and Cash Equivalents)*
- Market Cap uses **outstanding shares**, not **authorized shares**.

---

## 1.7 Volume and Liquidity

**Volume** is the number of shares (or units) traded during a period.

Volume matters for:
1. **Liquidity**: High-volume securities are easier to buy/sell at fair prices.
2. **Bid-ask spread**: Low-volume securities often have wider spreads (higher transaction
   cost for round-trip buy + sell).
3. **Price impact**: Large orders in low-volume securities move the price materially.
4. **Signal confirmation**: In technical analysis, price moves on high volume are
   considered more meaningful than moves on low volume.

**Caution**: Volume data can be unreliable across providers.
Some report only the primary exchange volume; others aggregate across all venues.

---

## 1.8 Bid, Ask, and Spread

| Term | Meaning |
|---|---|
| **Bid** | Highest price a buyer is willing to pay |
| **Ask** | Lowest price a seller is willing to accept |
| **Spread** | Ask − Bid |
| **Mid** | (Bid + Ask) / 2 |

The spread is an implicit transaction cost. For a round-trip trade (buy then sell),
you lose approximately one spread.

For highly liquid large-cap stocks (e.g., AAPL), the spread may be $0.01.
For illiquid small-caps, the spread can be several percent.

AURELIUS will initially use close prices (not bid/ask) for all calculations.
Bid/ask data is relevant for Milestone 14+ (backtesting with realistic transaction costs).

---

## 1.9 What to Study Next

After reading this chapter, the following topics prepare you for Milestone 1:

1. **Market Data Providers**: How yfinance works; what fields it returns.
2. **Corporate Actions**: Detailed mechanics of dividend adjustment factors.
3. **Data Quality**: What "bad data" looks like in practice (OHLC violations, gaps).
4. **Trading Calendar**: Why stock markets are closed on certain days; how to handle
   gaps in price series correctly.

---

*This chapter was created during Milestone 0. It will be expanded as later milestones
introduce additional concepts.*
