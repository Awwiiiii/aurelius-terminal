"""
tests.unit.domain.fundamental.test_period_matching
==================================================
Deterministic tests for period matching and strict two-point balance sheet averaging.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodLabel,
    FiscalPeriodType,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.enums import DiagnosticCode
from aurelius.domain.fundamental.period_matching import (
    MultiPeriodFactStore,
    calculate_two_point_average,
    get_prior_period,
    sort_periods_chronologically,
)
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


def test_sort_periods_chronologically():
    p1 = make_period("2022-12-31", fiscal_year=2022)
    p2 = make_period("2024-12-31", fiscal_year=2024)
    p3 = make_period("2023-12-31", fiscal_year=2023)

    sorted_p = sort_periods_chronologically([p2, p1, p3])
    assert [p.fiscal_year for p in sorted_p] == [2022, 2023, 2024]


def test_get_prior_period_annual():
    p2022 = make_period("2022-12-31", fiscal_year=2022)
    p2023 = make_period("2023-12-31", fiscal_year=2023)
    p2024 = make_period("2024-12-31", fiscal_year=2024)

    # Consecutive year available -> returns 2023
    assert (
        get_prior_period(p2024, [p2022, p2023, p2024], FiscalPeriodType.ANNUAL) == p2023
    )
    assert (
        get_prior_period(p2023, [p2022, p2023, p2024], FiscalPeriodType.ANNUAL) == p2022
    )
    assert (
        get_prior_period(p2022, [p2022, p2023, p2024], FiscalPeriodType.ANNUAL) is None
    )


def test_get_prior_period_annual_gap_returns_none():
    p2021 = make_period("2021-12-31", fiscal_year=2021)
    p2022 = make_period("2022-12-31", fiscal_year=2022)
    p2024 = make_period("2024-12-31", fiscal_year=2024)

    # 2024 with only 2021 available -> returns None (not 2021)
    assert get_prior_period(p2024, [p2021, p2024], FiscalPeriodType.ANNUAL) is None

    # Missing 2023 but having 2022 -> returns None
    assert get_prior_period(p2024, [p2022, p2024], FiscalPeriodType.ANNUAL) is None


def test_get_prior_period_quarterly_consecutive():
    q4_2024 = make_period(
        "2024-12-31",
        fiscal_year=2024,
        fiscal_period=FiscalPeriodLabel.Q4,
    )
    q1_2025 = make_period(
        "2025-03-31",
        fiscal_year=2025,
        fiscal_period=FiscalPeriodLabel.Q1,
    )
    q2_2025 = make_period(
        "2025-06-30",
        fiscal_year=2025,
        fiscal_period=FiscalPeriodLabel.Q2,
    )

    all_q = [q4_2024, q1_2025, q2_2025]

    # Q2 2025 -> Q1 2025
    prior_q2 = get_prior_period(q2_2025, all_q, FiscalPeriodType.QUARTERLY)
    assert prior_q2 is not None
    assert prior_q2.fiscal_year == 2025
    assert prior_q2.fiscal_period == FiscalPeriodLabel.Q1

    # Q1 2025 -> Q4 2024 (Year boundary transition)
    prior_q1 = get_prior_period(q1_2025, all_q, FiscalPeriodType.QUARTERLY)
    assert prior_q1 is not None
    assert prior_q1.fiscal_year == 2024
    assert prior_q1.fiscal_period == FiscalPeriodLabel.Q4


def test_get_prior_period_quarterly_gap_returns_none():
    q4_2024 = make_period(
        "2024-12-31",
        fiscal_year=2024,
        fiscal_period=FiscalPeriodLabel.Q4,
    )
    q2_2025 = make_period(
        "2025-06-30",
        fiscal_year=2025,
        fiscal_period=FiscalPeriodLabel.Q2,
    )

    # Q2 2025 with only Q4 2024 (missing Q1 2025) -> returns None
    assert (
        get_prior_period(q2_2025, [q4_2024, q2_2025], FiscalPeriodType.QUARTERLY)
        is None
    )


def test_get_prior_period_frequency_mismatch_returns_none():
    p_fy = make_period(
        "2024-12-31",
        fiscal_year=2024,
        fiscal_period=FiscalPeriodLabel.FY,
    )
    p_q1 = make_period(
        "2025-03-31",
        fiscal_year=2025,
        fiscal_period=FiscalPeriodLabel.Q1,
    )

    # Quarterly request on Annual period -> None
    assert get_prior_period(p_fy, [p_fy, p_q1], FiscalPeriodType.QUARTERLY) is None

    # Annual request comparing FY to quarterly candidate -> None
    assert get_prior_period(p_q1, [p_fy, p_q1], FiscalPeriodType.ANNUAL) is None


def test_two_point_average_strict():
    p_curr = make_period("2024-12-31")
    p_prior = make_period("2023-12-31")
    p_curr_inst = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    p_prior_inst = make_period("2023-12-31", period_type=PeriodType.INSTANT)

    fact_curr = make_fact(
        StatementType.BALANCE_SHEET, "300", p_curr_inst, CanonicalConcept.TOTAL_ASSETS
    )
    fact_prior = make_fact(
        StatementType.BALANCE_SHEET, "200", p_prior_inst, CanonicalConcept.TOTAL_ASSETS
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.BALANCE_SHEET, p_curr_inst, [fact_curr]),
            make_statement(StatementType.BALANCE_SHEET, p_prior_inst, [fact_prior]),
        ]
    )

    avg_val, diag, used_fb, facts = calculate_two_point_average(
        CanonicalConcept.TOTAL_ASSETS,
        p_curr,
        p_prior,
        store,
        allow_point_in_time_fallback=False,
    )
    assert avg_val == Decimal("250")
    assert diag is None
    assert used_fb is False
    assert len(facts) == 2


def test_two_point_average_missing_prior_default_unavailable():
    p_curr = make_period("2024-12-31")
    p_curr_inst = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_curr = make_fact(
        StatementType.BALANCE_SHEET, "300", p_curr_inst, CanonicalConcept.TOTAL_ASSETS
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p_curr_inst, [fact_curr])]
    )

    avg_val, diag, used_fb, facts = calculate_two_point_average(
        CanonicalConcept.TOTAL_ASSETS,
        p_curr,
        None,
        store,
        allow_point_in_time_fallback=False,
    )
    assert avg_val is None
    assert diag is not None
    assert diag.code == DiagnosticCode.INSUFFICIENT_PERIODS_FOR_AVERAGE
    assert used_fb is False


def test_two_point_average_fallback_mode():
    p_curr = make_period("2024-12-31")
    p_curr_inst = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_curr = make_fact(
        StatementType.BALANCE_SHEET, "300", p_curr_inst, CanonicalConcept.TOTAL_ASSETS
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p_curr_inst, [fact_curr])]
    )

    avg_val, diag, used_fb, facts = calculate_two_point_average(
        CanonicalConcept.TOTAL_ASSETS,
        p_curr,
        None,
        store,
        allow_point_in_time_fallback=True,
    )
    assert avg_val == Decimal("300")
    assert diag is not None
    assert diag.code == DiagnosticCode.POINT_IN_TIME_DENOMINATOR_FALLBACK
    assert used_fb is True
