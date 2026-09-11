# AURELIUS Finance Reference: Market Benchmarks, Volatility & Telemetry

## 1. Canonical Benchmarks

A market overview workspace requires benchmark indices that capture systemic macroeconomic performance across size, style, and risk dimensions. In AURELIUS, canonical benchmark identities are decoupled from provider routing symbols.

| Benchmark ID | Index Name | Segment | Weighting Methodology | Provider Symbol (Yahoo) |
|---|---|---|---|---|
| `SP500` | S&P 500 Index | Large-Cap Core | Float-adjusted market capitalization | `^GSPC` |
| `DOW` | Dow Jones Industrial Average | Mega-Cap Blue Chip | Price-weighted | `^DJI` |
| `NASDAQ` | Nasdaq Composite | Tech & Growth | Market capitalization | `^IXIC` |
| `RUSSELL2000` | Russell 2000 Index | Small-Cap Equities | Float-adjusted market capitalization | `^RUT` |
| `VIX` | CBOE Volatility Index | Implied Volatility | Option-implied variance strip | `^VIX` |

---

## 2. The Semantics of the CBOE VIX

### 2.1 What VIX Represents
The CBOE Volatility Index (`VIX`) is widely referred to as the market's "fear gauge." Economically, it represents the **market's expectation of 30-day forward annualized implied volatility** derived from out-of-the-money and at-the-money S&P 500 (`SPX`) index put and call options.

Formally, the VIX formula calculates implied variance $\sigma^2$ across option strike prices $K_i$:

$$\sigma^2 = \frac{2}{T} \sum_i \frac{\Delta K_i}{K_i^2} e^{R T} Q(K_i) - \frac{1}{T}\left(\frac{F}{K_0} - 1\right)^2$$

where $T$ is time to expiration, $F$ is forward index level, $K_0$ is the first strike below $F$, and $Q(K_i)$ is the midpoint option quote. The VIX index level is:

$$\text{VIX} = 100 \times \sqrt{\sigma^2}$$

### 2.2 Critical Financial Realities & Software Invariants
1. **Not a Currency Asset**:
   VIX is quoted in **volatility index points** (e.g. `15.73` means an annualized expected standard deviation of $\sim 15.73\%$ over the next 30 days). It must **NEVER** be displayed with currency symbols like `$` or `USD`.
2. **Not Realized Volatility**:
   VIX is forward-looking implied volatility derived from options pricing, not backward-looking historical/realized price standard deviation.
3. **Not Directly Investable**:
   An investor cannot directly buy shares of the VIX index. Traders access volatility exposure exclusively through derivatives: VIX futures, VIX options, or exchange-traded products (e.g. VXX, UVXY) that continuously roll futures contracts (and therefore suffer from roll yield decay during contango).
4. **Mean-Reverting & Negatively Correlated**:
   Equity returns and VIX changes exhibit strong negative correlation (typically $\rho \approx -0.7$ to $-0.8$) due to asymmetric hedging demand during equity drawdowns.

---

## 3. Market Movers Semantics

Market mover rankings identify securities exhibiting notable price velocity or abnormal liquidity during a trading session.

### 3.1 Ranking Categories
- **Gainers (`GAINERS`)**: Ranked by highest positive intraday percentage change ($\frac{P_{\text{current}} - P_{\text{prior close}}}{P_{\text{prior close}}} \times 100$).
- **Losers (`LOSERS`)**: Ranked by highest negative intraday percentage change.
- **Active (`ACTIVE`)**: Ranked by total reported session volume (whole-share count).

### 3.2 Strict Handling of Missing Volume
- Reported market volume represents a discrete count of whole shares traded during the trading day.
- If an upstream provider feed omits volume or returns null, AURELIUS preserves this as `None` / `null`.
- **Missing volume must NEVER be converted to or displayed as `0`**. An explicit zero volume signifies verified trading inactivity (e.g. trading halt), whereas missing volume represents telemetry omission.

### 3.3 Market Capitalization Invariant
- Market capitalization in Milestone 3 is sourced **strictly from provider-reported `marketCap`** (or `None` if omitted).
- AURELIUS does **not** independently reconstruct market cap as $P \times N_{\text{shares}}$ in M3, because shares outstanding definitions vary across share classes, dual-class structures, and treasury stock holdings.

### 3.4 Cross-Category Overlap
- Mover deduplication is applied strictly *per category*.
- Legitimate cross-category overlap (e.g. a high-beta large-cap stock like NVDA or TSLA simultaneously ranking among top gainers and highest volume active securities) is preserved. Dropping a security from Active simply because it gained would distort liquidity intelligence.

### 3.5 Initial Presentation Filters
To prevent terminal views from being dominated by extreme micro-cap or illiquid noise, AURELIUS applies initial presentation heuristics for gainers and losers:
- Minimum traded price: $\ge \$2.00$
- Minimum reported volume: $\ge 100,000$ shares (when volume is reported; missing volume is not dropped solely for lacking volume data).
These are explicitly documented as **presentation filters**, not universal financial criteria.

---

## 4. Market Operational Session Telemetry

### 4.1 US Equity Trading Sessions (Eastern Time)
- **Pre-Market**: 04:00 – 09:30 ET (thin liquidity, wide bid-ask spreads)
- **Regular Trading Hours (RTH)**: 09:30 – 16:00 ET (primary institutional liquidity)
- **After-Hours**: 16:00 – 20:00 ET (earnings reaction window)
- **Closed / Weekend**: Outside market operating windows, Saturdays, and Sundays.

### 4.2 Indicative Feed & Safe Fallback Telemetry
Without a direct exchange gateway (SIP/CTA feed) or an authoritative institutional holiday calendar, session state is indicative.

**Fallback Hierarchy**:
1. Check upstream provider session status (`yf.Market("US").status`).
2. If provider fails or returns unverified status:
   - Check day of week in `America/New_York`:
     - If Saturday or Sunday $\rightarrow$ `WEEKEND` (closed).
     - If weekday $\rightarrow$ **`UNKNOWN`** (never assert `REGULAR_OPEN` on a weekday without verified holiday calendar validation, as NYSE may be closed for holidays such as Good Friday, Memorial Day, Labor Day, Thanksgiving, or Christmas).
