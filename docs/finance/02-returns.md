# Finance Handbook — Chapter 2: Returns

> **Purpose**: Returns are the most fundamental quantity in financial analysis.
> Every performance measurement, risk metric, and factor model is built on returns.
> This chapter defines every return type used in AURELIUS precisely, with formulas,
> assumptions, examples, and known failure modes.

---

## 2.1 Why Returns Instead of Prices?

We almost always work with **returns** rather than raw prices because:

1. **Scale independence**: Returns are comparable across securities.
   A $5 stock gaining $1 and a $500 stock gaining $100 are not comparable by price change,
   but both have a 20% return — and that 20% is directly comparable.

2. **Stationarity**: Price series are typically non-stationary (they trend over time).
   Return series are closer to stationary, which is required for most statistical tests.

3. **Portfolio aggregation**: Portfolio returns are (approximately) the weighted sum of
   individual returns. Portfolio prices are not directly summable in the same way.

4. **Normalization**: Returns normalize for the passage of time and allow annualization.

---

## 2.2 Simple (Arithmetic) Return

### Formula

$$R_t = \frac{P_t - P_{t-1}}{P_{t-1}} = \frac{P_t}{P_{t-1}} - 1$$

Where:
- $P_t$ = price at time $t$ (the current period)
- $P_{t-1}$ = price at the previous period
- $R_t$ = return for period $t$

### Example

| Period | Price | Calculation | Return |
|---|---|---|---|
| t−1 | $100.00 | — | — |
| t | $103.50 | (103.50 / 100.00) − 1 | 3.50% |

### Units Convention in AURELIUS

Returns are stored and computed as **decimals**, not percentages:
- Correct: `R = 0.035` (meaning 3.5%)
- Wrong: `R = 3.5` (meaning 350% if treated as decimal)

This is critical for vector operations. When displaying to users, multiply by 100 and add `%`.

### Assumptions

1. The price series uses the same adjustment methodology throughout (e.g., all adj_close).
2. No transaction costs.
3. $P_{t-1} > 0$ (division by zero otherwise — log return handles this identically).

### When Simple Return Works Well

- Single-period analysis
- Portfolio return aggregation (weighted sum of positions)
- Most retail and institutional performance reporting conventions

### When Simple Return Has Limitations

- **Multi-period compounding**: You cannot simply add simple returns to get multi-period returns.
  If you earn +10% in period 1 and −10% in period 2, your cumulative return is NOT 0%:
  ```
  (1 + 0.10) × (1 − 0.10) = 1.10 × 0.90 = 0.99 → −1% cumulative return
  ```
  This is the **volatility drag** effect. Larger volatility produces larger drag.

- **Cross-asset comparison over long periods**: Arithmetic mean of simple returns
  overstates actual compound growth.

---

## 2.3 Logarithmic (Log) Return

### Formula

$$r_t = \ln\left(\frac{P_t}{P_{t-1}}\right) = \ln(P_t) - \ln(P_{t-1})$$

Where:
- $\ln$ = natural logarithm
- All other variables as defined in 2.2

### Example

| Period | Price | Calculation | Log Return |
|---|---|---|---|
| t−1 | $100.00 | — | — |
| t | $103.50 | ln(103.50 / 100.00) = ln(1.035) | 0.03440 (3.440%) |

Note: The simple return was 3.500%. The log return is slightly lower (3.440%).
The two are approximately equal for small returns; they diverge for large returns.

### Why Log Returns?

1. **Time additivity**: Log returns are additive over time.
   The multi-period log return is exactly the sum of single-period log returns:
   ```
   r(0→2) = r(0→1) + r(1→2) = ln(P1/P0) + ln(P2/P1) = ln(P2/P0)
   ```
   This property makes log returns natural for time-series analysis.

2. **Statistical properties**: Log returns are more normally distributed than simple
   returns for most assets. This matters for volatility estimation, VaR, and option pricing.

3. **Symmetry**: A +100% simple return (price doubles) and a −100% simple return (price
   goes to zero) are very asymmetric. Log returns are symmetric:
   ```
   Price doubles:  ln(2/1)   = +0.693
   Price halves:   ln(0.5/1) = −0.693
   ```

### Relationship Between Simple and Log Returns

$$r_t = \ln(1 + R_t) \approx R_t \text{ for small } R_t$$

The approximation is close for |R| < 5%, but diverges noticeably for large returns.

### When to Use Log Returns in AURELIUS

| Use Case | Return Type | Reason |
|---|---|---|
| Volatility estimation | Log | Additivity, better normality |
| Autocorrelation analysis | Log | Time additivity |
| Factor model signals | Log | Statistical convention |
| Performance reporting | Simple | Industry convention; intuitive |
| Portfolio aggregation | Simple | Weighted sum is exact only for simple returns |

### When Log Returns Fail

- When $P_t = 0$ (logarithm undefined). A stock going to zero means total loss.
  Log return goes to $-\infty$. Handle explicitly in code.
- When comparing to published performance figures (which almost always use simple returns).

---

## 2.4 Cumulative Return

The cumulative return over a period from $t=0$ to $t=T$ is:

### From Simple Returns

$$R_c = \prod_{t=1}^{T}(1 + R_t) - 1$$

This is the **compound** of all period returns. It equals:

$$R_c = \frac{P_T}{P_0} - 1$$

### From Log Returns

$$R_c = e^{\sum_{t=1}^T r_t} - 1 = e^{r_{0 \to T}} - 1$$

### Example

Three-period example:
```
Period 1: +5.00%   (simple R = 0.050)
Period 2: −3.00%   (simple R = −0.030)
Period 3: +2.00%   (simple R = 0.020)

Cumulative simple: (1.050)(0.970)(1.020) − 1 = 1.0388 − 1 = 3.88%
Cumulative log:    ln(1.050) + ln(0.970) + ln(1.020)
                 = 0.04879 + (−0.03046) + 0.01980 = 0.03813
                 e^0.03813 − 1 = 3.89%  ✓ (matches within rounding)

WRONG — do NOT do this: 5% + (−3%) + 2% = 4% ← this is NOT the correct cumulative return
```

---

## 2.5 Price Return vs. Total Return

> This is one of the most frequently confused distinctions in financial analysis.

### Price Return

Measures only capital appreciation. Ignores income (dividends, coupons):

$$R_{price} = \frac{P_t}{P_{t-1}} - 1$$

### Total Return

Includes all income distributions (dividends for stocks, coupons for bonds):

$$R_{total} = \frac{P_t + D_t}{P_{t-1}} - 1$$

Where $D_t$ = dividend paid during period $t$ (per share).

### Why This Matters

For a high-dividend company like Altria (MO) or a REIT like Realty Income (O),
dividends can represent 5–8% annual yield. Over a decade, ignoring dividends can
cause your performance analysis to understate total return by 50%+.

**The S&P 500 Index** is a price index (it tracks prices, not total return).
**The S&P 500 Total Return Index** (SPTR) includes reinvested dividends.
Many retail comparisons incorrectly compare a total-return strategy to the price index,
making the strategy look better than it is.

### Adjusted Close and Total Return — Important Caveats

When a provider's `adj_close` applies backward-proportional dividend adjustment:

```
The return computed as:  (adj_close[t] / adj_close[t-1]) - 1
...approximates the total return of a buy-and-hold investor
who reinvests dividends at the ex-dividend price.
```

**This is an approximation**, not exact total return, because:
1. Transaction costs for reinvestment are ignored.
2. Fractional shares are not modeled.
3. The timing of reinvestment is assumed to be at the ex-dividend open (provider-specific).
4. The methodology varies by provider.
5. Retroactive restatements can change historical adj_close values.

**Never state that `adj_close` universally equals total return.**
Always specify the provider and document the methodology.

---

## 2.6 Nominal Return vs. Real Return

### Nominal Return

The return as measured in the currency of the investment, without adjusting for inflation.
This is what AURELIUS computes by default.

### Real Return

The return adjusted for inflation:

$$R_{real} \approx R_{nominal} - \pi$$

More precisely (the Fisher equation):

$$(1 + R_{real}) = \frac{1 + R_{nominal}}{1 + \pi}$$

Where $\pi$ = inflation rate over the same period.

**Example**:
- Nominal return: 8% per year
- Inflation: 3% per year
- Real return: (1.08 / 1.03) − 1 ≈ 4.85% per year

**AURELIUS computes nominal returns.** If real return analysis is needed, inflation data
must be sourced separately (e.g., CPI data from FRED). This is a future milestone item.

---

## 2.7 Arithmetic Mean vs. Geometric Mean Return

Given a series of simple returns $R_1, R_2, \ldots, R_n$:

### Arithmetic Mean Return

$$\bar{R}_{arith} = \frac{1}{n}\sum_{i=1}^{n} R_i$$

### Geometric Mean Return

$$\bar{R}_{geo} = \left(\prod_{i=1}^{n}(1 + R_i)\right)^{1/n} - 1$$

### Which to Use?

| Purpose | Recommended | Reason |
|---|---|---|
| Expected single-period return | Arithmetic mean | Unbiased estimator for one period |
| Actual compound growth over time | Geometric mean | Reflects the path-dependence of compounding |
| Volatility drag quantification | Both | Difference shows impact of volatility |

The relationship between arithmetic and geometric mean:

$$\bar{R}_{geo} \approx \bar{R}_{arith} - \frac{\sigma^2}{2}$$

Where $\sigma^2$ is the variance of returns. Higher volatility → bigger gap between
arithmetic and geometric mean. This is the mathematical basis of volatility drag.

---

## 2.8 Annualization

Returns are often reported on an annualized basis regardless of the actual holding period.
This requires knowing the frequency of the data.

### Annualization Factor by Frequency

| Frequency | Periods per year (N) | Notes |
|---|---|---|
| Daily | 252 | Trading days, NOT calendar days |
| Weekly | 52 | |
| Monthly | 12 | |
| Quarterly | 4 | |

> **Critical**: Use **252 trading days per year** for daily financial data, NOT 365.
> This is the standard convention in finance. Using 365 produces a systematically
> incorrect annualized figure because prices don't move on weekends and holidays.
> Some practitioners use 260; 252 is the most common convention.

### Annualizing a Period Return

$$R_{annual} = (1 + R_{period})^N - 1$$

Where $N$ = number of periods in a year.

### Example

A position returned 5% over 3 months (one quarter).
Annualized: $(1 + 0.05)^4 - 1 = 1.2155 - 1 = 21.55\%$

**This is NOT** $4 \times 5\% = 20\%$ (that would be simple extrapolation, which ignores
compounding).

---

## 2.9 Implementation Notes for AURELIUS

### Numerical Representation

- Use `float64` (NumPy) for return time-series calculations.
- Use `Decimal` for monetary values (prices, dividends).
- Do NOT round return values at intermediate calculation steps.
- Only round at the API response boundary (typically 4–6 decimal places for display).

### Sign Convention

- Positive return: price increased
- Negative return: price decreased
- Express as decimal: 0.05 = 5%, -0.03 = -3%

### Edge Cases to Handle Explicitly

| Scenario | Handling |
|---|---|
| $P_{t-1} = 0$ | Raise `CalculationError` — undefined return |
| Price series length 0 | Raise `CalculationError` — cannot compute |
| Price series length 1 | Return empty array — no returns possible |
| NaN in price series | Raise `DataQualityError` — do not propagate NaN |
| Infinite value in result | Raise `CalculationError` — do not return `inf` |

---

## 2.10 Formulas Summary

| Concept | Formula |
|---|---|
| Simple Return | $R_t = P_t/P_{t-1} - 1$ |
| Log Return | $r_t = \ln(P_t/P_{t-1})$ |
| Cumulative Return | $R_c = P_T/P_0 - 1$ |
| Total Return (single period) | $R_{total} = (P_t + D_t)/P_{t-1} - 1$ |
| Real Return (Fisher) | $(1 + R_{real}) = (1 + R_{nom})/(1 + \pi)$ |
| Geometric Mean Return | $\bar{R}_{geo} = [\prod(1+R_i)]^{1/n} - 1$ |
| Annualized Return | $R_{annual} = (1 + R_{period})^N - 1$ |
| Volatility drag approx. | $\bar{R}_{geo} \approx \bar{R}_{arith} - \sigma^2/2$ |

---

## 2.11 What to Study Next

After this chapter, to prepare for Milestone 4 (Historical Market Analysis):

1. **Standard deviation of returns**: How volatility is computed from a return series.
2. **Rolling statistics**: How to apply return and volatility calculations over a rolling window.
3. **Drawdown**: How to compute the underwater curve from cumulative returns.
4. **NumPy and pandas**: The tools used to implement return calculations efficiently.

---

*This chapter was created during Milestone 0. Implementation of return calculations
begins in Milestone 4.*
