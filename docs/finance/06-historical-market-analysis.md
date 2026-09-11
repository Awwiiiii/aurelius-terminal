# 06 — Historical Market Analysis & Quantitative Methodology

This document outlines the institutional financial methodology, price series policies, return algorithms, volatility metrics, drawdown analytics, moving average indicator warm-up, and benchmark alignment standards implemented in **AURELIUS Milestone 4**.

---

## 1. Price Series Policy & Data Semantics

Financial analysis must maintain rigorous distinctions between nominal execution price levels and continuous economic return series:

1. **Nominal Raw Close (`close`)**:
   - **Usage**: Technical indicators (SMA 20, SMA 50, SMA 200, EMA 20) and Period Extremes ($P_{\text{high}}$, $P_{\text{low}}$).
   - **Rationale**: Support/resistance levels, nominal traded prices, moving average chart lines, and order execution levels exist in nominal currency space at the time of trade.
2. **Provider-Adjusted Close (`adj_close`)**:
   - **Usage**: Daily simple returns, cumulative return series, calendar-time CAGR, win rate, realized volatility, and peak-to-trough drawdowns.
   - **Rationale**: Prevents artificial discontinuities caused by corporate actions (e.g. stock splits and cash distributions). For instance, a 2-for-1 stock split cuts nominal share prices in half overnight without representing an economic loss of capital.
3. **Institutional Return Terminology**:
   - The period cumulative return derived from `adj_close` is formally named **Adjusted Price Return** (`adjusted_price_return`).
   - **PROHIBITION**: It is strictly prohibited from being called "Total Return" in AURELIUS documentation or interfaces. Provider `adj_close` is a modeled corporate-action proxy provided by third-party data feeds (such as Yahoo Finance) and does not account for investor-specific tax liabilities, execution commissions, dividend reinvestment slippage, or special spin-off accounting.

---

## 2. Configurable Time Horizons

AURELIUS supports nine standard time horizons:

| Horizon Code | Time Span Definition | Notes |
| :--- | :--- | :--- |
| `1M` | Elapsed 30 calendar days ($t_{\text{end}} - 30\text{d}$) | ~21 trading sessions |
| `3M` | Elapsed 90 calendar days ($t_{\text{end}} - 90\text{d}$) | ~63 trading sessions |
| `6M` | Elapsed 180 calendar days ($t_{\text{end}} - 180\text{d}$) | ~126 trading sessions |
| `YTD` | From January 1 of the current year | Calendar-year to date |
| `1Y` | Elapsed 365 calendar days ($t_{\text{end}} - 365\text{d}$) | ~252 trading sessions |
| `3Y` | Elapsed $3 \times 365$ calendar days | ~756 trading sessions |
| `5Y` | Elapsed $5 \times 365$ calendar days | ~1,260 trading sessions |
| `MAX` | Deep historical depth (~20 years / 7,305 calendar days) | Full provider available history |
| `CUSTOM` | Explicit user-supplied `start_date` and `end_date` | Validated for chronological order |

---

## 3. Return Metrics & Performance Algorithms

### 3.1 Daily Simple Returns
For an adjusted close series $P_0, P_1, \dots, P_{T-1}$:
$$R_t = \frac{P_t - P_{t-1}}{P_{t-1}} \quad \text{for } t \ge 1$$
$R_0$ emits `None` because the initial observation has no preceding price session.

### 3.2 Cumulative Return Series
The continuous performance rebased from the initial observation $P_0$:
$$\text{CumRet}_t = \frac{P_t - P_0}{P_0}$$

### 3.3 Calendar-Time CAGR
Annualized compounding is evaluated across elapsed **calendar time**, avoiding calendar/trading-day distortions:
$$\text{CAGR} = \left(\frac{P_{\text{end}}}{P_{\text{start}}}\right)^{\frac{365.2425}{\text{calendar\_days}}} - 1$$
- **Condition**: Only evaluated for horizons where $\text{calendar\_days} \ge 365$.
- For sub-year horizons ($< 365$ days), `cagr` emits `None` to prevent annualized compounding distortion from short-term market noise.

### 3.4 Win Rate
Evaluates the proportion of profitable sessions:
$$\text{Win Rate} = \frac{\text{positive\_days}}{\text{positive\_days} + \text{negative\_days}}$$
- **Rule**: Trading sessions with zero price change ($R_t == 0$) are **strictly excluded** from the win rate denominator.
- If $\text{positive\_days} + \text{negative\_days} == 0$, `win_rate` emits `None`.

---

## 4. Realized Volatility

### 4.1 Observation Count & Sample Standard Deviation
$N$ price observations yield $M = N - 1$ returns.
- **Minimum Requirements**: Two price observations produce 1 return, which is mathematically insufficient for sample standard deviation with Bessel correction ($M - 1 = 0$, division by zero).
- A minimum of **3 price observations (2 returns)** is required for sample volatility:
$$s = \sqrt{\frac{1}{M - 1} \sum_{i=1}^M \left(R_i - \bar{R}\right)^2}$$

### 4.2 Annualization
Using the standard US equity trading day convention of 252 sessions:
$$\sigma_{\text{annualized}} = s \times \sqrt{252}$$

### 4.3 Rolling Volatility
A $k$-day rolling volatility refers strictly to a sliding window of **$k$ daily returns**:
- Bars $0 \dots k-1$ emit `None` (fewer than $k$ returns available).
- Bar $k$ presents the first valid rolling volatility on returns $R_1 \dots R_k$.

---

## 5. Peak-to-Trough Drawdown & Recovery

### 5.1 Running Peak & Drawdown Series
On the provider-adjusted close series $P_t$:
$$\text{Peak}_t = \max_{0 \le s \le t} P_s$$
$$\text{DD}_t = \frac{P_t - \text{Peak}_t}{\text{Peak}_t} \le 0.0$$

### 5.2 Deterministic Max Drawdown (MDD) Tie-Breaking
$$\text{MDD} = \min_{0 \le t < T} \text{DD}_t$$
- **Trough Date**: If multiple sessions share the exact identical minimum drawdown percentage, choose the **earliest** trough date.
- **Peak Date**: For that selected trough, choose the **earliest** preceding peak session where $P_t = \text{Peak}_{\text{trough}}$.

### 5.3 Recovery Detection
- Evaluated strictly for sessions following the trough date ($t > t_{\text{trough}}$).
- The recovery date is the first session where $P_t \ge P_{\text{peak}}$.
- If price never recovers to or above the preceding peak before the series end:
  - `recovery_date = None`
  - `is_recovered = False`

---

## 6. Technical Moving Averages & Warm-Up

All moving averages are computed strictly on **nominal raw Close** prices.

### 6.1 Zero-Indexed Warm-Up Rules
For a moving average window $k=20$:
- Observations $0 \dots 18$ (first 19 observations): emit `None`.
- Observation 19 (the 20th observation): first valid $\text{SMA}_{20} = \frac{1}{20} \sum_{j=0}^{19} P_j$.
- Observation 20 onward: rolling $\text{SMA}_{20}$.

### 6.2 Exponential Moving Average ($\text{EMA}_{20}$)
- Observations $0 \dots 18$: emit `None`.
- Observation 19: initialized using $\text{SMA}_{20}$ over observations $0 \dots 19$.
- Observation 20 onward: recursive EMA calculation:
$$\alpha = \frac{2}{k + 1} = \frac{2}{21}$$
$$\text{EMA}_t = P_t \times \alpha + \text{EMA}_{t-1} \times (1 - \alpha)$$
*(Note: Does not require 21 observations; valid at observation 19).*

---

## 7. Benchmark Alignment & Correlation

Comparative performance is evaluated against the canonical US equity benchmark, the **S&P 500 (`^GSPC`)**:

1. **Inner Alignment**:
   - Dates where either the security or benchmark did not trade (holidays, exchange suspensions) are omitted.
2. **Common Base Date ($t_0$)**:
   - The earliest matched trading session is designated as the common base date. Both cumulative return series are rebased to 100.0 on this date.
3. **Synchronized Returns & Excess Return**:
   - Security return and benchmark return are measured across the matched dates.
   - $\text{Excess Return} = \text{Security Return} - \text{Benchmark Return}$.
4. **Pearson Correlation ($\rho$)**:
   - Calculated on matched daily simple return pairs over the common window:
$$\rho = \frac{\sum (R_{\text{sec}, i} - \bar{R}_{\text{sec}})(R_{\text{bmk}, i} - \bar{R}_{\text{bmk}})}{\sqrt{\sum (R_{\text{sec}, i} - \bar{R}_{\text{sec}})^2 \sum (R_{\text{bmk}, i} - \bar{R}_{\text{bmk}})^2}}$$
