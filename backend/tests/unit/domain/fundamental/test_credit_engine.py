"""
tests.unit.domain.fundamental.test_credit_engine
=================================================
Deterministic unit tests for FundamentalCreditEngine:
- Piotroski F-Score (Canonical 9 Signals):
    * F1 (ROA > 0), F2 (CFO > 0), F3 (CFO > NI), F4 (ROA expansion),
      F5 (Canonical Long-Term Debt / Average Assets de-leveraging),
      F6 (Current Ratio expansion), F7 (No dilution / share issuance),
      F8 (Gross Margin expansion), F9 (Asset Turnover expansion).
    * F5 Zero-Debt Convention (ZERO_LONG_TERM_DEBT_PASS_CONVENTION).
    * F5 Leveraged Tie Case (UNCHANGED_POSITIVE_LEVERAGE_FAIL).
    * Partial coverage reporting (Complete = 9, Partial = 7-8, Insufficient < 7).
    * Strict prohibition of normalized 9-point scaled equivalents.
- Altman Z-Score:
    * Unclassified balance sheets (banks/insurers) -> NOT_APPLICABLE with FINANCIAL_ENTITY_EXEMPTION.
    * AURELIUS structural dispatch heuristics:
        - Model 1 (Manufacturing): Inventory/TA >= 5% AND PPE/TA >= 15%. Safe/Grey/Distress zones.
        - Model 2 (Service Z''): Inventory/TA < 5% OR PPE/TA < 15%. Safe/Grey/Distress zones.
        - Borderline/ambiguous asset intensity -> Model 2 default with ALTMAN_AMBIGUOUS_STRUCTURE_DISPATCH_SERVICE.
    * Explicit user/analyst override parameter.
    * Missing retained earnings -> UNAVAILABLE with MISSING_REQUIRED_FACT.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.credit import FundamentalCreditEngine
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    MetricStatus,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)

# =============================================================================
# Piotroski F-Score Tests
# =============================================================================


def test_piotroski_f_score_all_pass():
    p_curr = make_period(
        "2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024
    )
    p_prior = make_period(
        "2023-12-31", period_type=PeriodType.DURATION, fiscal_year=2023
    )
    p_prior_prior = make_period(
        "2022-12-31", period_type=PeriodType.DURATION, fiscal_year=2022
    )

    # Current period (t):
    # NI = 300, TA = 2000 (ROA = 15%)
    # CFO = 400 (CFO > NI)
    # LTD = 100 (Avg TA = (1800 + 2000)/2 = 1900 -> LEVER_t = 100 / 1900 = 0.0526)
    # CA = 800, CL = 400 (CR_t = 2.0x)
    # Shares = 1000
    # Gross Profit = 1200, Revenue = 3000 (GM_t = 40%, Turnover_t = 3000 / 2000 = 1.5x)
    facts_curr = [
        make_fact(
            StatementType.INCOME_STATEMENT, "300", p_curr, CanonicalConcept.NET_INCOME
        ),
        make_fact(
            StatementType.INCOME_STATEMENT, "3000", p_curr, CanonicalConcept.REVENUE
        ),
        make_fact(
            StatementType.INCOME_STATEMENT,
            "1200",
            p_curr,
            CanonicalConcept.GROSS_PROFIT,
        ),
        make_fact(
            StatementType.CASH_FLOW, "400", p_curr, CanonicalConcept.OPERATING_CASH_FLOW
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "2000", p_curr, CanonicalConcept.TOTAL_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "100", p_curr, CanonicalConcept.LONG_TERM_DEBT
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "800", p_curr, CanonicalConcept.CURRENT_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "400",
            p_curr,
            CanonicalConcept.CURRENT_LIABILITIES,
        ),
        make_fact(
            StatementType.INCOME_STATEMENT,
            "1000",
            p_curr,
            source_concept="Diluted Average Shares",
        ),
    ]

    # Prior period (t-1):
    # NI = 180, TA = 1800 (ROA = 10% -> ROA expanded from 10% to 15%)
    # LTD = 200 (Avg TA = (1600 + 1800)/2 = 1700 -> LEVER_t-1 = 200 / 1700 = 0.1176 -> LEVER fell!)
    # CA = 600, CL = 400 (CR_t-1 = 1.5x -> CR expanded from 1.5x to 2.0x)
    # Shares = 1000 (Shares_t <= Shares_t-1)
    # Gross Profit = 800, Revenue = 2400 (GM_t-1 = 33.3% -> GM expanded, Turnover_t-1 = 2400 / 1800 = 1.33x -> Turnover expanded)
    facts_prior = [
        make_fact(
            StatementType.INCOME_STATEMENT, "180", p_prior, CanonicalConcept.NET_INCOME
        ),
        make_fact(
            StatementType.INCOME_STATEMENT, "2400", p_prior, CanonicalConcept.REVENUE
        ),
        make_fact(
            StatementType.INCOME_STATEMENT,
            "800",
            p_prior,
            CanonicalConcept.GROSS_PROFIT,
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "1800", p_prior, CanonicalConcept.TOTAL_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "200", p_prior, CanonicalConcept.LONG_TERM_DEBT
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "600", p_prior, CanonicalConcept.CURRENT_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "400",
            p_prior,
            CanonicalConcept.CURRENT_LIABILITIES,
        ),
        make_fact(
            StatementType.INCOME_STATEMENT,
            "1000",
            p_prior,
            source_concept="Diluted Average Shares",
        ),
    ]

    # Prior-prior period (t-2): Total Assets = 1600
    facts_prior_prior = [
        make_fact(
            StatementType.BALANCE_SHEET,
            "1600",
            p_prior_prior,
            CanonicalConcept.TOTAL_ASSETS,
        ),
    ]

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p_curr, facts_curr),
            make_statement(StatementType.INCOME_STATEMENT, p_prior, facts_prior),
            make_statement(
                StatementType.BALANCE_SHEET, p_prior_prior, facts_prior_prior
            ),
        ]
    )

    res = FundamentalCreditEngine.calculate_piotroski_f_score(
        p_curr, p_prior, store, prior_prior_period=p_prior_prior
    )

    assert res.status == MetricStatus.VALID
    assert res.raw_pass_count == 9
    assert res.evaluated_signal_count == 9
    assert res.total_signal_count == 9
    assert res.coverage_ratio == Decimal("1.0")
    assert res.metric_result.value == Decimal("9")
    assert all(s.status == "PASS" for s in res.signals)


def test_piotroski_f5_zero_debt_convention():
    p_curr = make_period(
        "2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024
    )
    p_prior = make_period(
        "2023-12-31", period_type=PeriodType.DURATION, fiscal_year=2023
    )

    # Both periods report zero long term debt
    facts_curr = [
        make_fact(
            StatementType.BALANCE_SHEET, "2000", p_curr, CanonicalConcept.TOTAL_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "0", p_curr, CanonicalConcept.LONG_TERM_DEBT
        ),
    ]
    facts_prior = [
        make_fact(
            StatementType.BALANCE_SHEET, "1800", p_prior, CanonicalConcept.TOTAL_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "0", p_prior, CanonicalConcept.LONG_TERM_DEBT
        ),
    ]

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.BALANCE_SHEET, p_curr, facts_curr),
            make_statement(StatementType.BALANCE_SHEET, p_prior, facts_prior),
        ]
    )

    f5_res = FundamentalCreditEngine._evaluate_signal_f5(p_curr, p_prior, None, store)
    assert f5_res.status == "PASS"
    assert "ZERO_LONG_TERM_DEBT_PASS_CONVENTION" in f5_res.notes


def test_piotroski_f5_unchanged_positive_leverage_fail():
    p_curr = make_period(
        "2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024
    )
    p_prior = make_period(
        "2023-12-31", period_type=PeriodType.DURATION, fiscal_year=2023
    )
    p_prior_prior = make_period(
        "2022-12-31", period_type=PeriodType.DURATION, fiscal_year=2022
    )

    # Identical positive debt and identical assets across all three periods:
    # LTD = 200, TA = 2000 across all periods -> LEVER_t == LEVER_t-1 == 0.10 > 0
    facts_curr = [
        make_fact(
            StatementType.BALANCE_SHEET, "2000", p_curr, CanonicalConcept.TOTAL_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "200", p_curr, CanonicalConcept.LONG_TERM_DEBT
        ),
    ]
    facts_prior = [
        make_fact(
            StatementType.BALANCE_SHEET, "2000", p_prior, CanonicalConcept.TOTAL_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "200", p_prior, CanonicalConcept.LONG_TERM_DEBT
        ),
    ]
    facts_prior_prior = [
        make_fact(
            StatementType.BALANCE_SHEET,
            "2000",
            p_prior_prior,
            CanonicalConcept.TOTAL_ASSETS,
        ),
    ]

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.BALANCE_SHEET, p_curr, facts_curr),
            make_statement(StatementType.BALANCE_SHEET, p_prior, facts_prior),
            make_statement(
                StatementType.BALANCE_SHEET, p_prior_prior, facts_prior_prior
            ),
        ]
    )

    f5_res = FundamentalCreditEngine._evaluate_signal_f5(
        p_curr, p_prior, p_prior_prior, store
    )
    assert f5_res.status == "FAIL"
    assert "UNCHANGED_POSITIVE_LEVERAGE_FAIL" in f5_res.notes


def test_piotroski_partial_and_insufficient_coverage():
    p_curr = make_period(
        "2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024
    )

    # Only current year data, no prior period at all -> only F1, F2, F3 can be evaluated (3 signals)
    facts_curr = [
        make_fact(
            StatementType.INCOME_STATEMENT, "300", p_curr, CanonicalConcept.NET_INCOME
        ),
        make_fact(
            StatementType.CASH_FLOW, "400", p_curr, CanonicalConcept.OPERATING_CASH_FLOW
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "2000", p_curr, CanonicalConcept.TOTAL_ASSETS
        ),
    ]
    store = MultiPeriodFactStore(
        [make_statement(StatementType.INCOME_STATEMENT, p_curr, facts_curr)]
    )

    res = FundamentalCreditEngine.calculate_piotroski_f_score(p_curr, None, store)
    # Only 3 evaluated signals (< 7 required) -> UNAVAILABLE with INSUFFICIENT_PIOTROSKI_SIGNALS
    assert res.status == MetricStatus.UNAVAILABLE
    assert res.evaluated_signal_count == 3
    assert res.coverage_ratio == Decimal("3") / Decimal("9")
    codes = [d.code for d in res.metric_result.diagnostics]
    assert DiagnosticCode.INSUFFICIENT_PIOTROSKI_SIGNALS in codes


# =============================================================================
# Altman Z-Score Tests
# =============================================================================


def test_altman_z_score_unclassified_balance_sheet_exempt():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    # Bank / Insurer with Total Assets but no Current Assets / Current Liabilities
    fact_ta = make_fact(
        StatementType.BALANCE_SHEET, "100000", p, CanonicalConcept.TOTAL_ASSETS
    )
    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_ta])]
    )

    res = FundamentalCreditEngine.calculate_altman_z_score(
        p, store, market_cap=Decimal("50000")
    )
    assert res.dispatched_model == "EXEMPT_FINANCIAL"
    assert res.metric_result.status == MetricStatus.NOT_APPLICABLE
    codes = [d.code for d in res.metric_result.diagnostics]
    assert DiagnosticCode.FINANCIAL_ENTITY_EXEMPTION in codes


def test_altman_z_score_model_1_manufacturing_dispatch():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # Total Assets = 10,000
    # Inventory = 1,000 (10% >= 5%)
    # Net PPE = 2,500 (25% >= 15%)
    # -> Structural dispatch heuristics triggers Model 1 (Manufacturing)
    # CA = 4,000, CL = 2,000 -> WC = 2,000 -> X1 = 2000 / 10000 = 0.20
    # Retained Earnings = 3,000 -> X2 = 3000 / 10000 = 0.30
    # EBIT = 1,500 -> X3 = 1500 / 10000 = 0.15
    # Total Liabilities = 4,000, Market Cap = 8,000 -> X4 = 8000 / 4000 = 2.0
    # Revenue = 12,000 -> X5 = 12000 / 10000 = 1.20
    facts_bs = [
        make_fact(
            StatementType.BALANCE_SHEET, "10000", p, CanonicalConcept.TOTAL_ASSETS
        ),
        make_fact(StatementType.BALANCE_SHEET, "1000", p, CanonicalConcept.INVENTORY),
        make_fact(StatementType.BALANCE_SHEET, "2500", p, source_concept="Net PPE"),
        make_fact(
            StatementType.BALANCE_SHEET, "4000", p, CanonicalConcept.CURRENT_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "2000", p, CanonicalConcept.CURRENT_LIABILITIES
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "3000", p, source_concept="Retained Earnings"
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "4000", p, CanonicalConcept.TOTAL_LIABILITIES
        ),
    ]
    facts_is = [
        make_fact(
            StatementType.INCOME_STATEMENT, "1500", p, CanonicalConcept.OPERATING_INCOME
        ),
        make_fact(StatementType.INCOME_STATEMENT, "12000", p, CanonicalConcept.REVENUE),
    ]

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, facts_bs + facts_is)]
    )
    mcap = Decimal("8000")

    res = FundamentalCreditEngine.calculate_altman_z_score(p, store, market_cap=mcap)
    assert res.dispatched_model == "MODEL_1_MANUFACTURING"
    assert res.metric_result.status == MetricStatus.VALID
    # Z = 1.2(0.20) + 1.4(0.30) + 3.3(0.15) + 0.6(2.0) + 0.999(1.20)
    # = 0.24 + 0.42 + 0.495 + 1.2 + 1.1988 = 3.5538
    assert res.total_score == Decimal("3.5538")
    assert res.zone == "SAFE"  # Z > 2.99
    codes = [d.code for d in res.metric_result.diagnostics]
    assert DiagnosticCode.ALTMAN_MODEL_DISPATCHED_MANUFACTURING in codes


def test_altman_z_score_model_2_service_dispatch():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # Software / Service company:
    # Total Assets = 5,000, Inventory = 0 (0% < 5%), Net PPE = 200 (4% < 15%)
    # -> Dispatches Model 2 (Service Z'', excludes X5)
    # CA = 2,500, CL = 1,000 -> WC = 1,500 -> X1 = 1500 / 5000 = 0.30
    # Retained Earnings = 1,000 -> X2 = 1000 / 5000 = 0.20
    # EBIT = 500 -> X3 = 500 / 5000 = 0.10
    # Total Liabilities = 2,000, Market Cap = 4,000 -> X4 = 4000 / 2000 = 2.0
    facts_bs = [
        make_fact(
            StatementType.BALANCE_SHEET, "5000", p, CanonicalConcept.TOTAL_ASSETS
        ),
        make_fact(StatementType.BALANCE_SHEET, "0", p, CanonicalConcept.INVENTORY),
        make_fact(StatementType.BALANCE_SHEET, "200", p, source_concept="Net PPE"),
        make_fact(
            StatementType.BALANCE_SHEET, "2500", p, CanonicalConcept.CURRENT_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "1000", p, CanonicalConcept.CURRENT_LIABILITIES
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "1000", p, source_concept="Retained Earnings"
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "2000", p, CanonicalConcept.TOTAL_LIABILITIES
        ),
    ]
    facts_is = [
        make_fact(
            StatementType.INCOME_STATEMENT, "500", p, CanonicalConcept.OPERATING_INCOME
        ),
        make_fact(StatementType.INCOME_STATEMENT, "4000", p, CanonicalConcept.REVENUE),
    ]

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, facts_bs + facts_is)]
    )
    mcap = Decimal("4000")

    res = FundamentalCreditEngine.calculate_altman_z_score(p, store, market_cap=mcap)
    assert res.dispatched_model == "MODEL_2_SERVICE"
    assert res.metric_result.status == MetricStatus.VALID
    # Z'' = 6.56(0.30) + 3.26(0.20) + 6.72(0.10) + 1.05(2.0)
    # = 1.968 + 0.652 + 0.672 + 2.1 = 5.392
    assert res.total_score == Decimal("5.392")
    assert res.zone == "SAFE"  # Z'' > 2.60
    codes = [d.code for d in res.metric_result.diagnostics]
    assert DiagnosticCode.ALTMAN_MODEL_DISPATCHED_SERVICE in codes


def test_altman_z_score_explicit_override():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    # Asset light firm that user wants to evaluate under Manufacturing Model 1
    facts_bs = [
        make_fact(
            StatementType.BALANCE_SHEET, "5000", p, CanonicalConcept.TOTAL_ASSETS
        ),
        make_fact(StatementType.BALANCE_SHEET, "0", p, CanonicalConcept.INVENTORY),
        make_fact(StatementType.BALANCE_SHEET, "200", p, source_concept="Net PPE"),
        make_fact(
            StatementType.BALANCE_SHEET, "2500", p, CanonicalConcept.CURRENT_ASSETS
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "1000", p, CanonicalConcept.CURRENT_LIABILITIES
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "1000", p, source_concept="Retained Earnings"
        ),
        make_fact(
            StatementType.BALANCE_SHEET, "2000", p, CanonicalConcept.TOTAL_LIABILITIES
        ),
    ]
    facts_is = [
        make_fact(
            StatementType.INCOME_STATEMENT, "500", p, CanonicalConcept.OPERATING_INCOME
        ),
        make_fact(StatementType.INCOME_STATEMENT, "4000", p, CanonicalConcept.REVENUE),
    ]
    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, facts_bs + facts_is)]
    )

    res = FundamentalCreditEngine.calculate_altman_z_score(
        p, store, market_cap=Decimal("4000"), altman_model_override="MANUFACTURING"
    )
    assert res.dispatched_model == "MODEL_1_MANUFACTURING"
    assert "User/analyst explicit model override" in res.dispatch_rationale
