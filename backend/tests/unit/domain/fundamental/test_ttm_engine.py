"""
backend/tests/unit/domain/fundamental/test_ttm_engine.py
=========================================================
Unit test suite for Milestone 7B.1 Period & TTM Engine.

Verifies:
  A. Four compatible quarterly periods -> correct TTM duration aggregation.
  B. Missing quarter -> unavailable.
  C. Incorrect quarter sequence -> unavailable.
  D. Fiscal-year boundary sequence (including non-calendar fiscal years).
  E. Instant facts are never summed (Balance Sheet validation).
  F. TTM period metadata (start_date, end_date, fiscal_year, fiscal_period=TTM).
  G. TTM provenance contains exactly the 4 contributing source facts.
  H. Decimal arithmetic preserved end-to-end without floating-point inaccuracies.
  I. Conflicting period facts surface CONFLICTING_PERIOD_FACTS diagnostic.
  J. CapEx sign normalization follows M7A canonical magnitude convention (abs(val)).
  K. TTM FCF = TTM CFO - TTM CapEx magnitude.
  + Edge cases: negative net income, zero revenue (division by zero), 52/53-week retailers, currency mismatch.
"""

from datetime import date
from decimal import Decimal

import pytest

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialConcept,
    FinancialFact,
    FinancialPeriod,
    FinancialStatement,
    FiscalPeriodLabel,
    PeriodType,
    Scale,
    StatementType,
    Unit,
)
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore
from aurelius.domain.fundamental.ttm import TTMEngine

# =============================================================================
# FIXTURE HELPERS
# =============================================================================


def make_quarter_period(
    fiscal_year: int,
    fiscal_period: FiscalPeriodLabel,
    start_date: date,
    end_date: date,
) -> FinancialPeriod:
    return FinancialPeriod(
        period_type=PeriodType.DURATION,
        start_date=start_date,
        end_date=end_date,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        is_period_label_source_reported=True,
        calendar_year=end_date.year,
    )


def make_fact(
    concept: CanonicalConcept,
    statement_type: StatementType,
    period: FinancialPeriod,
    value: Decimal | str | int,
    currency: Currency = Currency.USD,
    fact_id: str | None = None,
) -> FinancialFact:
    dec_val = Decimal(str(value))
    f_id = fact_id or f"fact_{concept.value}_{period.period_key}_{dec_val}"
    return FinancialFact(
        fact_id=f_id,
        company_id="TEST_CO",
        concept=FinancialConcept(
            source_concept=concept.value,
            canonical_concept=concept,
            statement_type=statement_type,
        ),
        period=period,
        value=dec_val,
        unit=Unit.CURRENCY,
        currency=currency,
        scale=Scale.UNITS,
    )


def make_statement(
    period: FinancialPeriod,
    statement_type: StatementType,
    facts: list[FinancialFact],
    currency: Currency = Currency.USD,
) -> FinancialStatement:
    return FinancialStatement(
        statement_id=f"stmt_{statement_type.value}_{period.period_key}",
        company_id="TEST_CO",
        statement_type=statement_type,
        period=period,
        currency=currency,
        facts=facts,
    )


# Standard 4 consecutive calendar quarters for FY 2024
@pytest.fixture
def standard_4_quarters() -> list[FinancialPeriod]:
    return [
        make_quarter_period(
            2024, FiscalPeriodLabel.Q1, date(2024, 1, 1), date(2024, 3, 31)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q2, date(2024, 4, 1), date(2024, 6, 30)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q3, date(2024, 7, 1), date(2024, 9, 30)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q4, date(2024, 10, 1), date(2024, 12, 31)
        ),
    ]


# =============================================================================
# TEST A & F & H: 4 COMPATIBLE QUARTERS -> CORRECT TTM, DATES & DECIMAL ARITHMETIC
# =============================================================================


def test_ttm_four_compatible_quarters_aggregation(
    standard_4_quarters: list[FinancialPeriod],
) -> None:
    """Test A, F, H: Exact 4-quarter duration aggregation, start/end dates, Decimal arithmetic."""
    q1, q2, q3, q4 = standard_4_quarters

    window, diag = TTMEngine.resolve_ttm_window(q4, standard_4_quarters)
    assert diag is None
    assert window is not None
    assert len(window.quarters) == 4

    # F. Verify TTM period metadata
    ttm_p = window.ttm_period
    assert ttm_p.period_type == PeriodType.DURATION
    assert ttm_p.start_date == date(2024, 1, 1)
    assert ttm_p.end_date == date(2024, 12, 31)
    assert ttm_p.fiscal_year == 2024
    assert ttm_p.fiscal_period == FiscalPeriodLabel.TTM
    assert ttm_p.period_key == "2024-12-31"

    # Create duration revenue facts with Decimal precision
    rev_facts = [
        make_fact(
            CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q1, "100.1234"
        ),
        make_fact(
            CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q2, "110.2345"
        ),
        make_fact(
            CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q3, "120.3456"
        ),
        make_fact(
            CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q4, "130.4567"
        ),
    ]

    stmts = [
        make_statement(q, StatementType.INCOME_STATEMENT, [f])
        for q, f in zip(standard_4_quarters, rev_facts, strict=True)
    ]
    store = MultiPeriodFactStore(stmts)

    res = TTMEngine.calculate_ttm_revenue(window, store)
    assert res.status == MetricStatus.VALID
    # H. Exact Decimal arithmetic: 100.1234 + 110.2345 + 120.3456 + 130.4567 = 461.1602
    assert res.value == Decimal("461.1602")
    assert res.currency == Currency.USD
    assert res.period == ttm_p
    assert res.metric_id == FundamentalMetricId.REVENUE
    assert res.category == MetricCategory.GROWTH


# =============================================================================
# TEST B: MISSING QUARTER -> UNAVAILABLE
# =============================================================================


def test_ttm_missing_quarter_unavailable() -> None:
    """Test B: When only 3 quarters are available, TTM is unavailable."""
    # Only Q2, Q3, Q4 available (missing Q1)
    quarters = [
        make_quarter_period(
            2024, FiscalPeriodLabel.Q2, date(2024, 4, 1), date(2024, 6, 30)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q3, date(2024, 7, 1), date(2024, 9, 30)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q4, date(2024, 10, 1), date(2024, 12, 31)
        ),
    ]

    window, diag = TTMEngine.resolve_ttm_window(quarters[2], quarters)
    assert window is None
    assert diag is not None
    assert diag.code == DiagnosticCode.INSUFFICIENT_PERIODS_FOR_TTM


def test_ttm_missing_fact_in_one_quarter_unavailable(
    standard_4_quarters: list[FinancialPeriod],
) -> None:
    """Test B2: 4 quarters exist, but one quarter is missing the required financial fact."""
    q1, q2, q3, q4 = standard_4_quarters
    window, _ = TTMEngine.resolve_ttm_window(q4, standard_4_quarters)
    assert window is not None

    # Q3 is missing revenue fact
    rev_facts = [
        make_fact(CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q1, "100"),
        make_fact(CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q2, "110"),
        # Q3 omitted!
        make_fact(CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q4, "130"),
    ]
    stmts = [
        make_statement(f.period, StatementType.INCOME_STATEMENT, [f]) for f in rev_facts
    ]
    store = MultiPeriodFactStore(stmts)

    res = TTMEngine.calculate_ttm_revenue(window, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert res.value is None
    assert any(d.code == DiagnosticCode.MISSING_REQUIRED_FACT for d in res.diagnostics)


# =============================================================================
# TEST C: INCORRECT QUARTER SEQUENCE -> UNAVAILABLE
# =============================================================================


def test_ttm_incorrect_quarter_sequence_gap() -> None:
    """Test C: Sequence has a gap (Q1, Q2, Q4 - missing Q3)."""
    quarters = [
        make_quarter_period(
            2024, FiscalPeriodLabel.Q1, date(2024, 1, 1), date(2024, 3, 31)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q2, date(2024, 4, 1), date(2024, 6, 30)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q4, date(2024, 10, 1), date(2024, 12, 31)
        ),
    ]
    window, diag = TTMEngine.resolve_ttm_window(quarters[2], quarters)
    assert window is None
    assert diag is not None
    assert diag.code == DiagnosticCode.INSUFFICIENT_PERIODS_FOR_TTM


# =============================================================================
# TEST D: FISCAL-YEAR BOUNDARY SEQUENCE
# =============================================================================


def test_ttm_fiscal_year_boundary_crossing() -> None:
    """Test D: Compatible sequence crossing fiscal year boundary (Q2, Q3, Q4 2024 -> Q1 2025)."""
    quarters = [
        make_quarter_period(
            2024, FiscalPeriodLabel.Q2, date(2024, 4, 1), date(2024, 6, 30)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q3, date(2024, 7, 1), date(2024, 9, 30)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q4, date(2024, 10, 1), date(2024, 12, 31)
        ),
        make_quarter_period(
            2025, FiscalPeriodLabel.Q1, date(2025, 1, 1), date(2025, 3, 31)
        ),
    ]

    window, diag = TTMEngine.resolve_ttm_window(quarters[3], quarters)
    assert diag is None
    assert window is not None
    assert window.ttm_period.fiscal_year == 2025
    assert window.ttm_period.start_date == date(2024, 4, 1)
    assert window.ttm_period.end_date == date(2025, 3, 31)


# =============================================================================
# TEST E: INSTANT FACTS ARE NEVER SUMMED
# =============================================================================


def test_ttm_instant_facts_never_summed(
    standard_4_quarters: list[FinancialPeriod],
) -> None:
    """Test E: Balance sheet facts cannot be aggregated via aggregate_duration_fact."""
    q1, q2, q3, q4 = standard_4_quarters
    window, _ = TTMEngine.resolve_ttm_window(q4, standard_4_quarters)
    assert window is not None

    facts = [
        make_fact(
            CanonicalConcept.CASH_AND_EQUIVALENTS,
            StatementType.BALANCE_SHEET,
            q,
            "1000",
        )
        for q in standard_4_quarters
    ]
    stmts = [
        make_statement(q, StatementType.BALANCE_SHEET, [f])
        for q, f in zip(standard_4_quarters, facts, strict=True)
    ]
    store = MultiPeriodFactStore(stmts)

    # Calling aggregate_duration_fact on Balance Sheet must raise ValueError
    with pytest.raises(
        ValueError, match="Cannot aggregate instant facts from BALANCE_SHEET"
    ):
        TTMEngine.aggregate_duration_fact(
            window=window,
            statement_type=StatementType.BALANCE_SHEET,
            concept=CanonicalConcept.CASH_AND_EQUIVALENTS,
            metric_id=FundamentalMetricId.WORKING_CAPITAL,
            category=MetricCategory.LIQUIDITY,
            fact_store=store,
            formula_id="TEST_SUM_INSTANT",
        )

    # Helper resolve_latest_instant_fact returns ONLY the latest anchor quarter fact (1000, not 4000)
    fact, diag = TTMEngine.resolve_latest_instant_fact(
        window,
        StatementType.BALANCE_SHEET,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
        store,
    )
    assert diag is None
    assert fact is not None
    assert fact.value == Decimal("1000")
    assert fact.period.period_key == q4.period_key


# =============================================================================
# TEST G: PROVENANCE CONTAINS EXACT CONTRIBUTING FACTS
# =============================================================================


def test_ttm_provenance_contains_exact_contributing_facts(
    standard_4_quarters: list[FinancialPeriod],
) -> None:
    """Test G: Provenance contains the 4 exact source fact_ids and source periods."""
    q1, q2, q3, q4 = standard_4_quarters
    window, _ = TTMEngine.resolve_ttm_window(q4, standard_4_quarters)
    assert window is not None

    rev_facts = [
        make_fact(
            CanonicalConcept.REVENUE,
            StatementType.INCOME_STATEMENT,
            q1,
            "100",
            fact_id="fact_rev_q1",
        ),
        make_fact(
            CanonicalConcept.REVENUE,
            StatementType.INCOME_STATEMENT,
            q2,
            "110",
            fact_id="fact_rev_q2",
        ),
        make_fact(
            CanonicalConcept.REVENUE,
            StatementType.INCOME_STATEMENT,
            q3,
            "120",
            fact_id="fact_rev_q3",
        ),
        make_fact(
            CanonicalConcept.REVENUE,
            StatementType.INCOME_STATEMENT,
            q4,
            "130",
            fact_id="fact_rev_q4",
        ),
    ]
    stmts = [
        make_statement(q, StatementType.INCOME_STATEMENT, [f])
        for q, f in zip(standard_4_quarters, rev_facts, strict=True)
    ]
    store = MultiPeriodFactStore(stmts)

    res = TTMEngine.calculate_ttm_revenue(window, store)
    assert res.status == MetricStatus.VALID
    assert res.provenance.formula_id == "FORMULA_TTM_REVENUE"
    assert res.provenance.methodology_version == "1.0.0"
    assert res.provenance.source_fact_ids == [
        "fact_rev_q1",
        "fact_rev_q2",
        "fact_rev_q3",
        "fact_rev_q4",
    ]
    assert res.provenance.source_periods == [
        "2024-03-31",
        "2024-06-30",
        "2024-09-30",
        "2024-12-31",
    ]


# =============================================================================
# TEST I: CONFLICTING PERIOD FACTS SURFACES DIAGNOSTIC
# =============================================================================


def test_ttm_conflicting_period_facts_diagnostic(
    standard_4_quarters: list[FinancialPeriod],
) -> None:
    """Test I: Two different values for the same canonical concept in one quarter yield CONFLICTING_PERIOD_FACTS."""
    q1, q2, q3, q4 = standard_4_quarters
    window, _ = TTMEngine.resolve_ttm_window(q4, standard_4_quarters)
    assert window is not None

    # Q2 has two conflicting facts: 110 vs 115
    f1 = make_fact(CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q1, "100")
    f2a = make_fact(
        CanonicalConcept.REVENUE,
        StatementType.INCOME_STATEMENT,
        q2,
        "110",
        fact_id="f2a",
    )
    f2b = make_fact(
        CanonicalConcept.REVENUE,
        StatementType.INCOME_STATEMENT,
        q2,
        "115",
        fact_id="f2b",
    )
    f3 = make_fact(CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q3, "120")
    f4 = make_fact(CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q4, "130")

    stmt1 = make_statement(q1, StatementType.INCOME_STATEMENT, [f1])
    stmt2 = make_statement(q2, StatementType.INCOME_STATEMENT, [f2a, f2b])
    stmt3 = make_statement(q3, StatementType.INCOME_STATEMENT, [f3])
    stmt4 = make_statement(q4, StatementType.INCOME_STATEMENT, [f4])

    store = MultiPeriodFactStore([stmt1, stmt2, stmt3, stmt4])

    res = TTMEngine.calculate_ttm_revenue(window, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.CONFLICTING_PERIOD_FACTS for d in res.diagnostics
    )


def test_ttm_duplicate_facts_deterministic_resolution(
    standard_4_quarters: list[FinancialPeriod],
) -> None:
    """Test duplicate facts with identical values resolve deterministically without error."""
    q1, q2, q3, q4 = standard_4_quarters
    window, _ = TTMEngine.resolve_ttm_window(q4, standard_4_quarters)
    assert window is not None

    f1 = make_fact(CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q1, "100")
    # Q2 has identical duplicate facts with same value 110
    f2a = make_fact(
        CanonicalConcept.REVENUE,
        StatementType.INCOME_STATEMENT,
        q2,
        "110",
        fact_id="f2a",
    )
    f2b = make_fact(
        CanonicalConcept.REVENUE,
        StatementType.INCOME_STATEMENT,
        q2,
        "110",
        fact_id="f2b",
    )
    f3 = make_fact(CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q3, "120")
    f4 = make_fact(CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q4, "130")

    store = MultiPeriodFactStore(
        [
            make_statement(q1, StatementType.INCOME_STATEMENT, [f1]),
            make_statement(q2, StatementType.INCOME_STATEMENT, [f2a, f2b]),
            make_statement(q3, StatementType.INCOME_STATEMENT, [f3]),
            make_statement(q4, StatementType.INCOME_STATEMENT, [f4]),
        ]
    )

    res = TTMEngine.calculate_ttm_revenue(window, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("460")


# =============================================================================
# TEST J & K: CAPEX NORMALIZATION & TTM FCF = TTM CFO - TTM CAPEX MAGNITUDE
# =============================================================================


def test_ttm_capex_normalization_and_fcf(
    standard_4_quarters: list[FinancialPeriod],
) -> None:
    """Test J & K: CapEx normalized to positive economic magnitude; TTM FCF = TTM CFO - TTM CapEx magnitude."""
    q1, q2, q3, q4 = standard_4_quarters
    window, _ = TTMEngine.resolve_ttm_window(q4, standard_4_quarters)
    assert window is not None

    # CFO facts
    cfo_facts = [
        make_fact(
            CanonicalConcept.OPERATING_CASH_FLOW, StatementType.CASH_FLOW, q1, "150"
        ),
        make_fact(
            CanonicalConcept.OPERATING_CASH_FLOW, StatementType.CASH_FLOW, q2, "160"
        ),
        make_fact(
            CanonicalConcept.OPERATING_CASH_FLOW, StatementType.CASH_FLOW, q3, "170"
        ),
        make_fact(
            CanonicalConcept.OPERATING_CASH_FLOW, StatementType.CASH_FLOW, q4, "180"
        ),
    ]
    # CapEx reported as negative values (standard GAAP cash flow outflow convention)
    capex_facts = [
        make_fact(
            CanonicalConcept.CAPITAL_EXPENDITURES, StatementType.CASH_FLOW, q1, "-30"
        ),
        make_fact(
            CanonicalConcept.CAPITAL_EXPENDITURES, StatementType.CASH_FLOW, q2, "-40"
        ),
        make_fact(
            CanonicalConcept.CAPITAL_EXPENDITURES, StatementType.CASH_FLOW, q3, "-50"
        ),
        make_fact(
            CanonicalConcept.CAPITAL_EXPENDITURES, StatementType.CASH_FLOW, q4, "-60"
        ),
    ]

    stmts = [
        make_statement(q, StatementType.CASH_FLOW, [cfo, capex])
        for q, cfo, capex in zip(
            standard_4_quarters, cfo_facts, capex_facts, strict=True
        )
    ]
    store = MultiPeriodFactStore(stmts)

    # Verify TTM CFO: 150 + 160 + 170 + 180 = 660
    cfo_res = TTMEngine.calculate_ttm_cfo(window, store)
    assert cfo_res.status == MetricStatus.VALID
    assert cfo_res.value == Decimal("660")

    # J. Verify TTM CapEx: abs(-30) + abs(-40) + abs(-50) + abs(-60) = 180
    capex_res = TTMEngine.calculate_ttm_capex(window, store)
    assert capex_res.status == MetricStatus.VALID
    assert capex_res.value == Decimal("180")

    # K. Verify TTM FCF = 660 - 180 = 480
    fcf_res = TTMEngine.calculate_ttm_fcf(window, store)
    assert fcf_res.status == MetricStatus.VALID
    assert fcf_res.value == Decimal("480")
    assert fcf_res.currency == Currency.USD
    assert len(fcf_res.provenance.source_fact_ids) == 8


# =============================================================================
# EDGE CASES: NEGATIVE VALUES, ZERO VALUES, 52/53-WEEK, ROLLING WINDOWS
# =============================================================================


def test_ttm_negative_net_income_losses(
    standard_4_quarters: list[FinancialPeriod],
) -> None:
    """Test company with operating losses across quarters."""
    q1, q2, q3, q4 = standard_4_quarters
    window, _ = TTMEngine.resolve_ttm_window(q4, standard_4_quarters)
    assert window is not None

    ni_facts = [
        make_fact(
            CanonicalConcept.NET_INCOME, StatementType.INCOME_STATEMENT, q1, "-100"
        ),
        make_fact(
            CanonicalConcept.NET_INCOME, StatementType.INCOME_STATEMENT, q2, "50"
        ),
        make_fact(
            CanonicalConcept.NET_INCOME, StatementType.INCOME_STATEMENT, q3, "-25"
        ),
        make_fact(
            CanonicalConcept.NET_INCOME, StatementType.INCOME_STATEMENT, q4, "-75"
        ),
    ]
    stmts = [
        make_statement(q, StatementType.INCOME_STATEMENT, [f])
        for q, f in zip(standard_4_quarters, ni_facts, strict=True)
    ]
    store = MultiPeriodFactStore(stmts)

    res = TTMEngine.calculate_ttm_net_income(window, store)
    assert res.status == MetricStatus.VALID
    # -100 + 50 - 25 - 75 = -150
    assert res.value == Decimal("-150")


def test_ttm_zero_revenue_division_by_zero_margin(
    standard_4_quarters: list[FinancialPeriod],
) -> None:
    """Test zero TTM revenue produces ZERO_DENOMINATOR diagnostic on margins."""
    q1, q2, q3, q4 = standard_4_quarters
    window, _ = TTMEngine.resolve_ttm_window(q4, standard_4_quarters)
    assert window is not None

    rev_facts = [
        make_fact(CanonicalConcept.REVENUE, StatementType.INCOME_STATEMENT, q, "0")
        for q in standard_4_quarters
    ]
    gp_facts = [
        make_fact(CanonicalConcept.GROSS_PROFIT, StatementType.INCOME_STATEMENT, q, "0")
        for q in standard_4_quarters
    ]
    stmts = [
        make_statement(q, StatementType.INCOME_STATEMENT, [r, gp])
        for q, r, gp in zip(standard_4_quarters, rev_facts, gp_facts, strict=True)
    ]
    store = MultiPeriodFactStore(stmts)

    res = TTMEngine.calculate_ttm_gross_margin(window, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(d.code == DiagnosticCode.ZERO_DIVISION for d in res.diagnostics)


def test_ttm_currency_mismatch_diagnostic(
    standard_4_quarters: list[FinancialPeriod],
) -> None:
    """Test currency mismatch between quarters returns CURRENCY_MISMATCH."""
    q1, q2, q3, q4 = standard_4_quarters
    window, _ = TTMEngine.resolve_ttm_window(q4, standard_4_quarters)
    assert window is not None

    rev_facts = [
        make_fact(
            CanonicalConcept.REVENUE,
            StatementType.INCOME_STATEMENT,
            q1,
            "100",
            currency=Currency.USD,
        ),
        make_fact(
            CanonicalConcept.REVENUE,
            StatementType.INCOME_STATEMENT,
            q2,
            "110",
            currency=Currency.USD,
        ),
        make_fact(
            CanonicalConcept.REVENUE,
            StatementType.INCOME_STATEMENT,
            q3,
            "120",
            currency=Currency.EUR,
        ),  # mismatch!
        make_fact(
            CanonicalConcept.REVENUE,
            StatementType.INCOME_STATEMENT,
            q4,
            "130",
            currency=Currency.USD,
        ),
    ]
    stmts = [
        make_statement(
            q, StatementType.INCOME_STATEMENT, [f], currency=f.currency or Currency.USD
        )
        for q, f in zip(standard_4_quarters, rev_facts, strict=True)
    ]
    store = MultiPeriodFactStore(stmts)

    res = TTMEngine.calculate_ttm_revenue(window, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(d.code == DiagnosticCode.CURRENCY_MISMATCH for d in res.diagnostics)


def test_ttm_52_53_week_retail_calendar() -> None:
    """Test 52/53-week retail calendar with non-standard quarter end dates."""
    # E.g. Walmart/Target style: Q1 ends May 4, Q2 ends Aug 3, Q3 ends Nov 2, Q4 ends Feb 1
    retail_quarters = [
        make_quarter_period(
            2024, FiscalPeriodLabel.Q1, date(2023, 2, 5), date(2023, 5, 4)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q2, date(2023, 5, 5), date(2023, 8, 3)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q3, date(2023, 8, 4), date(2023, 11, 2)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q4, date(2023, 11, 3), date(2024, 2, 1)
        ),
    ]

    window, diag = TTMEngine.resolve_ttm_window(retail_quarters[3], retail_quarters)
    assert diag is None
    assert window is not None
    assert window.ttm_period.start_date == date(2023, 2, 5)
    assert window.ttm_period.end_date == date(2024, 2, 1)
    assert window.ttm_period.fiscal_year == 2024


def test_ttm_find_all_ttm_windows_rolling() -> None:
    """Test scanning 6 quarters yields exactly 3 trailing TTM windows."""
    quarters = [
        make_quarter_period(
            2024, FiscalPeriodLabel.Q1, date(2024, 1, 1), date(2024, 3, 31)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q2, date(2024, 4, 1), date(2024, 6, 30)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q3, date(2024, 7, 1), date(2024, 9, 30)
        ),
        make_quarter_period(
            2024, FiscalPeriodLabel.Q4, date(2024, 10, 1), date(2024, 12, 31)
        ),
        make_quarter_period(
            2025, FiscalPeriodLabel.Q1, date(2025, 1, 1), date(2025, 3, 31)
        ),
        make_quarter_period(
            2025, FiscalPeriodLabel.Q2, date(2025, 4, 1), date(2025, 6, 30)
        ),
    ]

    windows = TTMEngine.find_all_ttm_windows(quarters)
    assert len(windows) == 3
    # Window 0: Q1 2024 to Q4 2024
    assert windows[0].anchor_quarter.period_key == "2024-12-31"
    # Window 1: Q2 2024 to Q1 2025
    assert windows[1].anchor_quarter.period_key == "2025-03-31"
    # Window 2: Q3 2024 to Q2 2025
    assert windows[2].anchor_quarter.period_key == "2025-06-30"


def test_ttm_instant_pair_beginning_ending() -> None:
    """Test TTMEngine.resolve_instant_pair retrieves Q(t) and Q(t-4)."""
    # 5 quarters: Q4 2023, Q1 2024, Q2 2024, Q3 2024, Q4 2024
    q_prior = make_quarter_period(
        2023, FiscalPeriodLabel.Q4, date(2023, 10, 1), date(2023, 12, 31)
    )
    q1 = make_quarter_period(
        2024, FiscalPeriodLabel.Q1, date(2024, 1, 1), date(2024, 3, 31)
    )
    q2 = make_quarter_period(
        2024, FiscalPeriodLabel.Q2, date(2024, 4, 1), date(2024, 6, 30)
    )
    q3 = make_quarter_period(
        2024, FiscalPeriodLabel.Q3, date(2024, 7, 1), date(2024, 9, 30)
    )
    q4 = make_quarter_period(
        2024, FiscalPeriodLabel.Q4, date(2024, 10, 1), date(2024, 12, 31)
    )
    all_quarters = [q_prior, q1, q2, q3, q4]

    window, _ = TTMEngine.resolve_ttm_window(q4, all_quarters)
    assert window is not None

    facts = [
        make_fact(
            CanonicalConcept.TOTAL_ASSETS, StatementType.BALANCE_SHEET, q_prior, "800"
        ),
        make_fact(
            CanonicalConcept.TOTAL_ASSETS, StatementType.BALANCE_SHEET, q4, "1200"
        ),
    ]
    stmts = [make_statement(f.period, StatementType.BALANCE_SHEET, [f]) for f in facts]
    store = MultiPeriodFactStore(stmts)

    end_fact, beg_fact, diags = TTMEngine.resolve_instant_pair(
        window,
        StatementType.BALANCE_SHEET,
        CanonicalConcept.TOTAL_ASSETS,
        store,
        all_periods=all_quarters,
    )
    assert diags == []
    assert end_fact is not None
    assert end_fact.value == Decimal("1200")
    assert beg_fact is not None
    assert beg_fact.value == Decimal("800")
