# Trailing Twelve Months (TTM) & Advanced Fundamental Analysis Engine

## 1. Overview and Purpose

In financial terminal analysis, **Trailing Twelve Months (TTM)** represents the operational performance of an enterprise aggregated over the most recent four consecutive compatible fiscal quarters. TTM bridges the latency between annual 10-K reporting cycles, delivering up-to-date insight into top-line growth, operating profitability, and cash flow generation without calendar distortions.

Milestone 7B.1 (`M7B.1`) establishes the **Period & TTM Engine** for AURELIUS, enforcing institutional-grade guarantees regarding period sequencing, fiscal boundary continuity, audit provenance, and missing-data safety.

---

## 2. Core Concepts: Duration vs. Instant Facts

Financial facts are fundamentally divided into two temporal measurement categories:

| Dimension | `DURATION` (Interval) | `INSTANT` (Point-in-Time) |
| :--- | :--- | :--- |
| **Financial Nature** | Measured across an interval $[t_0, t_1]$. | Measured at an exact point in time $t$. |
| **Statements** | Income Statement, Cash Flow Statement. | Balance Sheet. |
| **TTM Aggregation Rule** | **Summed** across exactly 4 compatible quarters: $\sum_{i=0}^3 Q(t-i)$. | **NEVER summed**. Sourced from anchor quarter $Q(t)$ or evaluated as two-point beginning/ending pairs. |
| **Examples** | Revenue, Operating Income, Operating Cash Flow, CapEx. | Cash & Equivalents, Current Assets, Debt, Stockholders' Equity. |

> [!WARNING]
> Summing Balance Sheet line items across quarters is mathematically invalid and financially misleading (e.g. summing Cash across 4 quarters results in quadrupled liquidity). The AURELIUS `TTMEngine.aggregate_duration_fact` explicitly rejects `StatementType.BALANCE_SHEET` by raising a `ValueError`.

---

## 3. Strict Quarter Sequencing & Fiscal Calendar Handling

### Compatible Quarter Sequencing
To construct a valid TTM window ending at anchor quarter $Q(t)$, the engine enforces strict chronological and fiscal backward linking:

$$[Q(t-3), Q(t-2), Q(t-1), Q(t)]$$

Where each $Q(t-i-1)$ must be verified as the strictly preceding consecutive fiscal quarter to $Q(t-i)$:
- $Q2 \to Q1$ (Same Fiscal Year)
- $Q3 \to Q2$ (Same Fiscal Year)
- $Q4 \to Q3$ (Same Fiscal Year)
- $Q1(Y) \to Q4(Y-1)$ (Fiscal Year Boundary Crossing)

### Respecting Non-Calendar Fiscal Years
AURELIUS does not assume issuers use calendar quarters (ending in March, June, September, December).
- **Apple Inc. (AAPL)**: Fiscal year ends in September (Q1 ends Dec, Q2 ends Mar, Q3 ends Jun, Q4 ends Sep).
- **Retailers (52/53-week calendars, e.g. Walmart, Target)**: Fiscal year ends in January/February; quarter end dates vary by week counts (e.g. May 4, Aug 3, Nov 2, Feb 1).

Because quarter linking operates on authoritative `fiscal_year` and `fiscal_period` labels with date chronological checks, non-standard fiscal calendars are handled natively without fuzzy date heuristics.

### Strict Date Validation
- Quarter end dates must be strictly monotonic:
  $$\text{end\_date}(Q_{t-3}) < \text{end\_date}(Q_{t-2}) < \text{end\_date}(Q_{t-1}) < \text{end\_date}(Q_{t})$$
- Fuzzy date tolerances (e.g., $\pm 15$ days) are forbidden.
- Authoritative metadata is never guessed or inferred if missing from source disclosures.

---

## 4. TTM Aggregation Rules

### Standard Duration Line Items
For duration facts, the 4 quarterly amounts are summed using exact `Decimal` arithmetic:
- **TTM Revenue** = $Q(t-3) + Q(t-2) + Q(t-1) + Q(t)$
- **TTM Gross Profit** = $Q(t-3) + Q(t-2) + Q(t-1) + Q(t)$
- **TTM Operating Income** = $Q(t-3) + Q(t-2) + Q(t-1) + Q(t)$
- **TTM Net Income** = $Q(t-3) + Q(t-2) + Q(t-1) + Q(t)$
- **TTM Operating Cash Flow (CFO)** = $Q(t-3) + Q(t-2) + Q(t-1) + Q(t)$

### Capital Expenditures Normalization
Under GAAP/IFRS, Capital Expenditures in Cash Flow statements are frequently reported as negative numbers (representing cash outflows). Following the M7A canonical convention:
1. Each quarterly CapEx fact is normalized to its positive economic magnitude: $|\text{CapEx}_i|$.
2. **TTM CapEx** = $\sum_{i=0}^3 |\text{CapEx}_{Q(t-i)}|$.
3. Original source signs and values are preserved in audit provenance notes.

### Free Cash Flow (FCF)
$$\text{TTM Free Cash Flow} = \text{TTM Operating Cash Flow} - \text{TTM CapEx Magnitude}$$
Requires both TTM CFO and TTM CapEx to be valid; otherwise returns `UNAVAILABLE`.

### Ratios and Margins
- **TTM Gross Profit Margin** = $\frac{\text{TTM Gross Profit}}{\text{TTM Revenue}}$
- **TTM Operating Margin** = $\frac{\text{TTM Operating Income}}{\text{TTM Revenue}}$
- **TTM Net Profit Margin** = $\frac{\text{TTM Net Income}}{\text{TTM Revenue}}$
- **TTM FCF Margin** = $\frac{\text{TTM Free Cash Flow}}{\text{TTM Revenue}}$
- **TTM FCF Conversion** = $\frac{\text{TTM Free Cash Flow}}{\text{TTM Net Income}}$ (defined only when $\text{TTM Net Income} \neq 0$)
- **TTM CFO to Net Income** = $\frac{\text{TTM Operating Cash Flow}}{\text{TTM Net Income}}$ (defined only when $\text{TTM Net Income} \neq 0$)

---

## 5. Instant Facts (Balance Sheet) Helpers

For balance sheet analysis accompanying TTM metrics:
1. **Latest Quarter-End Instant**: Evaluates point-in-time facts (Cash, Working Capital, Debt) as of the anchor quarter cutoff date ($Q(t)$).
2. **Two-Point Instant Pair**: Retrieves the ending balance sheet fact at $Q(t)$ and the beginning balance sheet fact at $Q(t-4)$ (the quarter-end immediately preceding $Q(t-3)$), enabling strict 2-point balance sheet averaging across the full 12-month duration.

---

## 6. Audit Provenance Tracking

Every calculated TTM metric contains an immutable `MetricProvenance` record:
- `formula_id`: Identifies the exact algorithm (e.g. `FORMULA_TTM_REVENUE`, `FORMULA_TTM_FCF`, `FORMULA_TTM_CAPEX`).
- `methodology_version`: `"1.0.0"`.
- `source_fact_ids`: List of all contributing quarterly fact IDs (e.g., 4 IDs for duration sums, 8 IDs for FCF).
- `source_concepts`: Canonical and reported concept tags consumed.
- `source_periods`: The exact four period keys of the contributing quarters.
- `provider`: Primary reporting vendor (e.g. `"yahoo_finance"`).
- `methodology_notes`: Explicit notes documenting aggregation rules, CapEx magnitude normalization, or fallback states.

---

## 7. Missing Data & Conflicting Fact Safety

AURELIUS strictly enforces **zero data hallucination**:
- **Missing Quarters**: If an issuer only has 3 quarters of history, or if there is a gap in reporting (e.g. Q1, Q2, Q4 with Q3 missing), TTM returns `MetricStatus.UNAVAILABLE` with `INSUFFICIENT_PERIODS_FOR_TTM`.
- **Missing Line Items**: If any single quarter within an otherwise valid 4-quarter window lacks a required concept, the TTM metric returns `UNAVAILABLE` with `MISSING_REQUIRED_FACT`. Missing values are **never treated as zero**.
- **Conflicting Facts**: If multiple filings or data providers report conflicting numerical values for the same canonical concept in the same quarter, the engine refuses to guess and emits `CONFLICTING_PERIOD_FACTS`. Identical duplicate facts are deterministically deduplicated.
- **Currency Mismatches**: If facts across quarters differ in reported currency, the engine surfaces `CURRENCY_MISMATCH`.

---

## 8. Diagnostic Classifications

| Diagnostic Code | Condition |
| :--- | :--- |
| `INSUFFICIENT_PERIODS_FOR_TTM` | Fewer than 4 consecutive quarterly periods available to form a TTM window. |
| `INCOMPATIBLE_TTM_QUARTERS` | Quarter sequence has gaps, missing fiscal metadata, or non-monotonic dates. |
| `MISSING_REQUIRED_FACT` | One or more quarters within the 4-quarter window is missing the required financial fact. |
| `CONFLICTING_PERIOD_FACTS` | Conflicting values reported for the same canonical concept and period key. |
| `CURRENCY_MISMATCH` | Inconsistent reporting currencies across the contributing quarters. |
| `ZERO_DIVISION` | Denominator is zero (e.g., zero revenue or zero net income). |

---

## 9. Current Limitations & Non-Goals

- **Interim Period Lengths**: Designed for standard 3-month quarterly reporting and 52/53-week retailers. Semiannual foreign issuers (e.g. some European / Asian 6-month reporting companies) require future semiannual TTM methodology.
- **Restatements**: Prior-period restatements reported in subsequent 10-Q disclosures are reflected when provider filings supply restated quarterly facts.
- **Non-Goals (M8+)**: Valuation multiples (P/E, EV/EBITDA), WACC, DCF modeling, peer screening, and multi-factor models are non-goals for M7B.1 and are deferred to subsequent milestones.
