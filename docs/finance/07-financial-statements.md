# 07 — Financial Statement Infrastructure

This chapter defines the financial statement domain architecture, period semantics, canonical normalization rules, and data quality standards implemented in **Milestone 6** of AURELIUS.

---

## 1. Core Engineering Principle

> **CORRECTNESS > COMPLETENESS > SPEED**

Financial statements represent statutory corporate disclosures governed by accounting frameworks (US GAAP, IFRS). Unlike market quote telemetry, financial statement facts require exact numerical precision, explicit temporal measurement semantics, strict provenance tracking, and defensive data quality guardrails.

---

## 2. Temporal Period Semantics: Instant vs. Duration

A fundamental distinction in financial accounting is whether an economic fact is measured at a static point in time or over an elapsed duration:

| Statement | Temporal Nature | Period Type | Example Concepts | Boundary Semantics |
|---|---|---|---|---|
| **Balance Sheet** | Point in time (Snapshot) | `INSTANT` | Cash, Accounts Receivable, Total Assets, Total Debt | Evaluated strictly as of `instant_date` (e.g. `2024-09-30`). Cannot possess duration intervals. |
| **Income Statement** | Elapsed interval (Flow) | `DURATION` | Revenues, Operating Expenses, Net Income | Measured over `[start_date, end_date]`. Evaluates performance across the reporting window. |
| **Cash Flow Statement** | Elapsed interval (Flow) | `DURATION` | Operating Cash Flow, CapEx, Financing Cash Flow | Measured over `[start_date, end_date]`. Evaluates cash generation and capital changes. |

In AURELIUS:
- A `FinancialPeriod` model enforces strict exclusivity: `INSTANT` periods require `instant_date` and forbid `end_date` or `start_date`.
- `DURATION` periods require `end_date` and forbid `instant_date`.
- Any attempt to create an instant fact with duration bounds, or a duration fact with an instant cutoff, is rejected at the domain boundary.

---

## 3. Date Semantics: Filing Date vs. Period End

A common flaw in rudimentary financial software is collapsing the disclosure submission date into the fiscal period cutoff date. In reality, these are semantically distinct dates:

- **Report Period End (`report_period_end`)**: The accounting cutoff date representing the end of the fiscal quarter or fiscal year (e.g., September 28 for Apple's fiscal year).
- **Filing Date (`filing_date`)**: The legal calendar date when the Form 10-K or 10-Q was formally transmitted to the SEC EDGAR repository (e.g., October 31).

Collapsing these dates introduces lookahead bias into historical backtests and fundamental valuation models. In AURELIUS, `filing_date` and `report_period_end` are represented as distinct fields on the `Filing` entity. When a data provider does not supply an authoritative filing date, AURELIUS preserves `filing_date = None` rather than fabricating it from the period end.

---

## 4. FinancialFact Semantics & Exact Arithmetic

Every financial observation in AURELIUS is modeled as an immutable `FinancialFact`:

```
FinancialFact = {
    fact_id: str,
    company_id: str,
    concept: FinancialConcept,
    value: Decimal,
    unit: Unit,
    currency: Currency | None,
    scale: Scale,
    period: FinancialPeriod,
    filing: Filing | None,
    dimensions: dict[str, str],
    provenance: dict[str, str],
    is_restated: bool
}
```

### Exact `Decimal` Representation
To prevent IEEE-754 floating-point rounding errors (e.g. `0.1 + 0.2 != 0.3` or large billion-dollar integer precision loss), all fact values in the domain and service layers are stored strictly as Python `Decimal` instances. Provider conversions parse numeric strings directly into `Decimal(str(int(val)))` or `Decimal(str(val))`.

### Orthogonal Unit, Currency, and Scale
Measurement attributes are kept strictly orthogonal:
1. **Unit**: `CURRENCY`, `SHARES`, `RATIO`, `PERCENT`.
2. **Currency**: ISO-4217 code (e.g., `USD`, `EUR`, `JPY`). Required when `unit == Unit.CURRENCY`; forbidden (`None`) when `unit == Unit.SHARES`.
3. **Scale**: Magnitude multiplier applied to reported numbers (`UNITS` $\times 10^0$, `THOUSANDS` $\times 10^3$, `MILLIONS` $\times 10^6$, `BILLIONS` $\times 10^9$).

---

## 5. Conservative Canonical Concept Normalization

Companies and data vendors use thousands of disparate tags to report similar concepts (e.g., `"Total Revenue"`, `"Revenues"`, `"Sales"`, `"Operating Revenue"`). AURELIUS maps these vendor-specific labels to a conservative canonical taxonomy (`CanonicalConcept`):

### Income Statement Taxonomy
- `REVENUE`: Gross economic inflows from core operations.
- `COST_OF_REVENUE`: Direct expenses incurred to generate goods/services.
- `GROSS_PROFIT`: `REVENUE - COST_OF_REVENUE`.
- `OPERATING_EXPENSES`: Ongoing administrative and selling overhead.
- `RESEARCH_AND_DEVELOPMENT`: Direct investments in innovation and software.
- `SELLING_GENERAL_AND_ADMINISTRATIVE`: Overhead, sales commissions, management costs.
- `OPERATING_INCOME`: Operating profit before non-operating items and taxes.
- `OTHER_INCOME_EXPENSE`: Net non-operating income, interest, and investment gains/losses.
- `PRETAX_INCOME`: EBT (Earnings Before Taxes).
- `INCOME_TAX_EXPENSE`: Provision for income taxes.
- `NET_INCOME`: Bottom-line corporate profit attributable to shareholders.
- `EBITDA`: Only populated when directly reported by the provider. **Never calculated or synthesized in M6.**

### Balance Sheet Taxonomy
- `CASH_AND_EQUIVALENTS`: Highly liquid cash balances and short-term paper.
- `SHORT_TERM_INVESTMENTS`: Liquid marketable securities maturing $< 1$ year.
- `ACCOUNTS_RECEIVABLE`: Amounts owed by customers for delivered goods.
- `INVENTORY`: Raw materials, work-in-progress, and finished goods.
- `CURRENT_ASSETS`: Total assets convertible to cash within 1 operating cycle.
- `PROPERTY_PLANT_EQUIPMENT`: Net capital equipment, land, and factories.
- `GOODWILL`: Premium paid over fair market value in past acquisitions.
- `INTANGIBLE_ASSETS`: Patents, trademarks, and capitalized software.
- `TOTAL_ASSETS`: Complete sum of all current and non-current economic resources.
- `ACCOUNTS_PAYABLE`: Short-term liabilities owed to suppliers.
- `CURRENT_LIABILITIES`: Obligations due within 1 calendar year.
- `LONG_TERM_DEBT`: Funded debt obligations maturing $> 1$ year.
- `TOTAL_LIABILITIES`: Total economic obligations to creditors.
- `STOCKHOLDERS_EQUITY`: Net residual book value attributable to equity holders.

### Cash Flow Taxonomy
- `OPERATING_CASH_FLOW`: Cash generated from core customer operations.
- `CAPITAL_EXPENDITURES`: Capital investments in property, plant, and equipment.
- `INVESTING_CASH_FLOW`: Net cash used for capital investments, acquisitions, and securities.
- `FINANCING_CASH_FLOW`: Net cash from debt issuance/paydown, dividends, and share buybacks.
- `NET_CHANGE_IN_CASH`: Net change in cash and cash equivalents across the period.

### Handling Unmapped Concepts
Any provider row that does not conservatively match a canonical concept retains its exact provider label with `canonical_concept = None`. All raw reported line items remain accessible to analysts without data loss.

---

## 6. Data Quality Standards

### Rule 1: Missing $\ne$ Zero
Under no circumstance does AURELIUS convert missing or `NaN` financial data to `0` or `0.0`. Missing line items remain omitted from domain facts and evaluate to `None` / `null` in API schemas and `—` in terminal tables.

### Rule 2: No Fabrication of EBITDA
EBITDA is an unstandardized non-GAAP metric that varies across corporate disclosures. In Milestone 6, EBITDA is strictly mapped if and only if the underlying source explicitly reports an `"EBITDA"` or `"Normalized EBITDA"` line item. It is never synthetically calculated.

### Rule 3: Source-Reported vs. Derived Fiscal Periods
Fiscal period labels (`FY`, `Q1`, `Q2`, `Q3`, `Q4`) explicitly declare whether the label was supplied directly by the data source (`is_period_label_source_reported = True`) or derived (`False`). Periods are never inferred merely from calendar month ends.

### Rule 4: Non-Corporate Asset Rejection
Financial statements are legally filed exclusively by corporate operating entities. Requesting financial statements for non-corporate assets (ETFs like `SPY`, Indices like `^GSPC`, Cryptocurrencies like `BTC-USD`) raises a domain `DataNotFoundError` explaining that non-corporate instruments do not report statutory financial statements.

---

## 7. Known Provider Limitations (Yahoo Finance)

1. **Unofficial Data Feed**: yfinance scrapes public endpoints where row labels and availability vary across tickers and restatements.
2. **Missing SEC Accession Numbers**: yfinance statements do not provide EDGAR accession numbers (`accession_number`) or exact filing dates (`filing_date`). These fields remain `None`.
3. **Limited Historical Depth**: Annual statements generally offer 4–5 fiscal years; quarterly statements offer 4–8 fiscal quarters.
4. **Statement Alignment**: Balance sheet dates occasionally differ from income statement dates by several calendar days depending on corporate fiscal week cycles (e.g. 52/53-week fiscal years).
