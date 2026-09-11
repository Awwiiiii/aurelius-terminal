# Market Data Infrastructure & Financial Foundations

This document establishes the financial and technical principles governing market data ingestion, normalization, and interpretation in AURELIUS.

---

## 1. Raw vs. Adjusted Prices

### Unadjusted (Raw) OHLC
Every transaction on an exchange occurs at an exact, unadjusted price agreed upon between buyers and sellers at a specific moment in time.
- **Open**: Price of the first executed transaction during regular trading hours.
- **High**: Highest transaction price recorded during the session.
- **Low**: Lowest transaction price recorded during the session.
- **Close**: Price established by the official closing auction or final trade.

In AURELIUS, raw OHLC fields (`open`, `high`, `low`, `close`) **always remain completely unadjusted**. They preserve the historical reality of trade execution, which is required for technical analysis, order simulation, and slippage modeling.

### Provider Adjusted Close (`adj_close`)
Corporate actions alter a stock's capital structure or return capital to shareholders:
1. **Stock Splits**: A 2-for-1 split doubles the number of outstanding shares and halves the market price per share, leaving company market capitalization unchanged.
2. **Cash Dividends**: When a company pays a cash dividend, its equity value drops by the total dividend payout on the ex-dividend date.

To prevent artificial downward price jumps from being interpreted as market crashes, data providers calculate an **Adjusted Close**.

### Crucial Financial Clarification: `adj_close` vs. Exact Investor Total Return
In AURELIUS, `adj_close` represents a **provider-specific adjusted historical close** (from Yahoo Finance).
> **Important Financial Principle:**
> `adj_close` must **not** automatically be interpreted as an exact investor total-return series.
>
> **Why?**
> 1. **Dividend Reinvestment Timing:** Yahoo Finance applies a standard backward multiplicative proportional factor ($P_{adj} = P \times \prod (1 - D_t / P_t)$). Actual investor total return depends on whether, when, and at what price dividends are actually reinvested.
> 2. **Taxation:** Cash dividends are subject to withholding taxes and capital gains taxes that vary by jurisdiction, investor tax status, and account type.
> 3. **Special Distributions & Spin-offs:** Different data providers handle spin-offs, rights offerings, and irregular capital distributions differently.
>
> Therefore, while `adj_close` is an indispensable proxy for long-term historical performance and return calculations, quantitative researchers must remain aware of provider adjustment assumptions.

### Semantics of `is_adjusted`
In AURELIUS:
- `is_adjusted = True` on an `OHLCVSeries` denotes that provider-adjusted closing prices are populated in each bar's `adj_close` field.
- **`is_adjusted` does NOT imply that OHLC fields themselves have been altered.** Raw OHLC remains strictly raw historical transaction data.

---

## 2. Market Volume

### Whole-Share Volume Reporting
In AURELIUS domain entities:
```python
volume: int
```
- **Aggregate Market Volume**: Financial exchanges (NYSE, NASDAQ, etc.) and consolidated market feeds report aggregate trading volume as a whole-share count.
- **Retail Fractional Shares**: While fractional shares can exist internally within broker-dealer balance sheets and fractional retail trading platforms, standard exchange-cleared and provider-aggregated volumes are whole numbers.
- **Numerical Correctness**: Modeling volume as an integer prevents floating-point inaccuracies in trade volume totals and VWAP calculations.

---

## 3. Market Intervals & Time Aggregation

In Milestone 1, bar aggregation is explicitly restricted to daily bars:
```python
MarketInterval.DAILY = "1d"
```
- Multi-period aggregations (weekly `1wk`, monthly `1mo`) require dedicated handling of calendar holidays, partial weeks at month ends, weekend cutoffs, and multi-session alignment.
- M1 isolates daily bars to establish rigorous baseline verification before introducing multi-period aggregation logic in subsequent milestones.

---

## 4. Provider Delay Semantics & Limitations

### Provider Status
Milestone 1 utilizes Yahoo Finance as an initial, zero-cost data provider.
- **Provider Delays**: While quotes on free feeds are typically delayed by 15–20 minutes during market trading hours, certain securities or market states may reflect near real-time pricing.
- We do not make an unconditional factual claim that *every* quote is delayed; rather, `is_delayed` represents known provider feed characteristics and service limitations.
- **Selective Retries**: Transient transport timeouts and HTTP 5xx errors are retried up to 1 time after a 2-second backoff. Non-transient errors (HTTP 429 rate limits, empty datasets, invalid tickers, domain quality failures) are **never** retried, protecting system stability and network efficiency.
