"""
tests.unit.domain.fundamental.test_roic_engine
==============================================
Unit tests for ROIC, NOPAT, ETR, and Invested Capital calculation engine.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
    Unit,
)
from aurelius.domain.fundamental.engines.roic import ROICEngine
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


def test_effective_tax_rate_normal():
    period = make_period("2024-12-31")
    f_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "25.0",
        period,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )
    f_ebt = make_fact(
        StatementType.INCOME_STATEMENT, "100.0", period, CanonicalConcept.PRETAX_INCOME
    )

    stmt = make_statement(StatementType.INCOME_STATEMENT, period, [f_tax, f_ebt])
    store = MultiPeriodFactStore([stmt])

    res = ROICEngine.calculate_effective_tax_rate(period, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("0.25")
    assert res.unit == Unit.PERCENT
    assert len(res.diagnostics) == 0


def test_effective_tax_rate_missing_tax():
    period = make_period("2024-12-31")
    f_ebt = make_fact(
        StatementType.INCOME_STATEMENT, "100.0", period, CanonicalConcept.PRETAX_INCOME
    )

    stmt = make_statement(StatementType.INCOME_STATEMENT, period, [f_ebt])
    store = MultiPeriodFactStore([stmt])

    res = ROICEngine.calculate_effective_tax_rate(period, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert res.value is None
    assert any(
        d.code == DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE for d in res.diagnostics
    )


def test_effective_tax_rate_boundary_ebt_non_positive():
    period = make_period("2024-12-31")
    f_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "10.0",
        period,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )
    f_ebt = make_fact(
        StatementType.INCOME_STATEMENT, "-50.0", period, CanonicalConcept.PRETAX_INCOME
    )

    stmt = make_statement(StatementType.INCOME_STATEMENT, period, [f_tax, f_ebt])
    store = MultiPeriodFactStore([stmt])

    res = ROICEngine.calculate_effective_tax_rate(period, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert res.value is None
    assert any(
        d.code == DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE for d in res.diagnostics
    )


def test_effective_tax_rate_boundary_tax_non_positive():
    period = make_period("2024-12-31")
    f_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "-5.0",
        period,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )
    f_ebt = make_fact(
        StatementType.INCOME_STATEMENT, "100.0", period, CanonicalConcept.PRETAX_INCOME
    )

    stmt = make_statement(StatementType.INCOME_STATEMENT, period, [f_tax, f_ebt])
    store = MultiPeriodFactStore([stmt])

    res = ROICEngine.calculate_effective_tax_rate(period, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE for d in res.diagnostics
    )


def test_effective_tax_rate_boundary_ge_one():
    period = make_period("2024-12-31")
    f_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "105.0",
        period,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )
    f_ebt = make_fact(
        StatementType.INCOME_STATEMENT, "100.0", period, CanonicalConcept.PRETAX_INCOME
    )

    stmt = make_statement(StatementType.INCOME_STATEMENT, period, [f_tax, f_ebt])
    store = MultiPeriodFactStore([stmt])

    res = ROICEngine.calculate_effective_tax_rate(period, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE for d in res.diagnostics
    )


def test_nopat_normal():
    period = make_period("2024-12-31")
    f_ebit = make_fact(
        StatementType.INCOME_STATEMENT,
        "120.0",
        period,
        CanonicalConcept.OPERATING_INCOME,
    )
    f_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "20.0",
        period,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )
    f_ebt = make_fact(
        StatementType.INCOME_STATEMENT, "100.0", period, CanonicalConcept.PRETAX_INCOME
    )

    stmt = make_statement(
        StatementType.INCOME_STATEMENT, period, [f_ebit, f_tax, f_ebt]
    )
    store = MultiPeriodFactStore([stmt])

    # ETR = 20 / 100 = 0.20
    # NOPAT = 120 * (1 - 0.20) = 96.0
    res = ROICEngine.calculate_nopat(period, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("96.0")
    assert res.unit == Unit.CURRENCY
    assert len(res.diagnostics) == 0


def test_nopat_negative_operating_profit():
    period = make_period("2024-12-31")
    f_ebit = make_fact(
        StatementType.INCOME_STATEMENT,
        "-50.0",
        period,
        CanonicalConcept.OPERATING_INCOME,
    )
    f_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "10.0",
        period,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )
    f_ebt = make_fact(
        StatementType.INCOME_STATEMENT, "100.0", period, CanonicalConcept.PRETAX_INCOME
    )

    stmt = make_statement(
        StatementType.INCOME_STATEMENT, period, [f_ebit, f_tax, f_ebt]
    )
    store = MultiPeriodFactStore([stmt])

    # ETR = 0.10. NOPAT = -50 * 0.90 = -45.0
    res = ROICEngine.calculate_nopat(period, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("-45.0")
    assert any(
        d.code == DiagnosticCode.NEGATIVE_OPERATING_PROFIT for d in res.diagnostics
    )


def test_invested_capital_and_roic_normal():
    p_prior = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )
    p_curr = make_period("2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024)
    p_curr_dur = make_period(
        "2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024
    )

    # 2023 BS: Debt = 200, Equity = 800, Cash = 100 -> IC_beg = 900
    f_debt_23 = make_fact(
        StatementType.BALANCE_SHEET, "200.0", p_prior, CanonicalConcept.LONG_TERM_DEBT
    )
    f_eq_23 = make_fact(
        StatementType.BALANCE_SHEET,
        "800.0",
        p_prior,
        CanonicalConcept.STOCKHOLDERS_EQUITY,
    )
    f_cash_23 = make_fact(
        StatementType.BALANCE_SHEET,
        "100.0",
        p_prior,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
    )

    # 2024 BS: Debt = 300, Equity = 900, Cash = 100 -> IC_end = 1100
    f_debt_24 = make_fact(
        StatementType.BALANCE_SHEET, "300.0", p_curr, CanonicalConcept.LONG_TERM_DEBT
    )
    f_eq_24 = make_fact(
        StatementType.BALANCE_SHEET,
        "900.0",
        p_curr,
        CanonicalConcept.STOCKHOLDERS_EQUITY,
    )
    f_cash_24 = make_fact(
        StatementType.BALANCE_SHEET,
        "100.0",
        p_curr,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
    )

    # 2024 IS: EBIT = 200, EBT = 200, Tax = 40 -> ETR = 0.20 -> NOPAT = 160
    f_ebit = make_fact(
        StatementType.INCOME_STATEMENT,
        "200.0",
        p_curr_dur,
        CanonicalConcept.OPERATING_INCOME,
    )
    f_ebt = make_fact(
        StatementType.INCOME_STATEMENT,
        "200.0",
        p_curr_dur,
        CanonicalConcept.PRETAX_INCOME,
    )
    f_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "40.0",
        p_curr_dur,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )

    s_bs_23 = make_statement(
        StatementType.BALANCE_SHEET, p_prior, [f_debt_23, f_eq_23, f_cash_23]
    )
    s_bs_24 = make_statement(
        StatementType.BALANCE_SHEET, p_curr, [f_debt_24, f_eq_24, f_cash_24]
    )
    s_is_24 = make_statement(
        StatementType.INCOME_STATEMENT, p_curr_dur, [f_ebit, f_ebt, f_tax]
    )

    store = MultiPeriodFactStore([s_bs_23, s_bs_24, s_is_24])

    # Average IC = (900 + 1100) / 2 = 1000.0
    # ROIC = 160 / 1000 = 0.16 (16%)
    res = ROICEngine.calculate_roic(p_curr_dur, p_prior, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("0.16")
    assert res.unit == Unit.PERCENT


def test_roic_point_in_time_fallback():
    p_curr_dur = make_period(
        "2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024
    )

    # 2024 BS: Debt = 300, Equity = 900, Cash = 200 -> IC_end = 1000
    f_debt_24 = make_fact(
        StatementType.BALANCE_SHEET,
        "300.0",
        p_curr_dur,
        CanonicalConcept.LONG_TERM_DEBT,
    )
    f_eq_24 = make_fact(
        StatementType.BALANCE_SHEET,
        "900.0",
        p_curr_dur,
        CanonicalConcept.STOCKHOLDERS_EQUITY,
    )
    f_cash_24 = make_fact(
        StatementType.BALANCE_SHEET,
        "200.0",
        p_curr_dur,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
    )

    # 2024 IS: EBIT = 100, EBT = 100, Tax = 20 -> NOPAT = 80
    f_ebit = make_fact(
        StatementType.INCOME_STATEMENT,
        "100.0",
        p_curr_dur,
        CanonicalConcept.OPERATING_INCOME,
    )
    f_ebt = make_fact(
        StatementType.INCOME_STATEMENT,
        "100.0",
        p_curr_dur,
        CanonicalConcept.PRETAX_INCOME,
    )
    f_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "20.0",
        p_curr_dur,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )

    s_bs_24 = make_statement(
        StatementType.BALANCE_SHEET, p_curr_dur, [f_debt_24, f_eq_24, f_cash_24]
    )
    s_is_24 = make_statement(
        StatementType.INCOME_STATEMENT, p_curr_dur, [f_ebit, f_ebt, f_tax]
    )
    store = MultiPeriodFactStore([s_bs_24, s_is_24])

    # Fallback disabled -> UNAVAILABLE
    res_no_fb = ROICEngine.calculate_roic(
        p_curr_dur, None, store, allow_point_in_time_fallback=False
    )
    assert res_no_fb.status == MetricStatus.UNAVAILABLE

    # Fallback enabled -> VALID (80 / 1000 = 0.08)
    res_fb = ROICEngine.calculate_roic(
        p_curr_dur, None, store, allow_point_in_time_fallback=True
    )
    assert res_fb.status == MetricStatus.VALID
    assert res_fb.value == Decimal("0.08")
    assert any(
        d.code == DiagnosticCode.POINT_IN_TIME_DENOMINATOR_FALLBACK
        for d in res_fb.diagnostics
    )


def test_roic_non_positive_invested_capital():
    p_curr_dur = make_period(
        "2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024
    )

    # Debt = 100, Equity = 200, Cash = 500 -> IC = 100 + 200 - 500 = -200
    f_debt_24 = make_fact(
        StatementType.BALANCE_SHEET,
        "100.0",
        p_curr_dur,
        CanonicalConcept.LONG_TERM_DEBT,
    )
    f_eq_24 = make_fact(
        StatementType.BALANCE_SHEET,
        "200.0",
        p_curr_dur,
        CanonicalConcept.STOCKHOLDERS_EQUITY,
    )
    f_cash_24 = make_fact(
        StatementType.BALANCE_SHEET,
        "500.0",
        p_curr_dur,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
    )

    f_ebit = make_fact(
        StatementType.INCOME_STATEMENT,
        "100.0",
        p_curr_dur,
        CanonicalConcept.OPERATING_INCOME,
    )
    f_ebt = make_fact(
        StatementType.INCOME_STATEMENT,
        "100.0",
        p_curr_dur,
        CanonicalConcept.PRETAX_INCOME,
    )
    f_tax = make_fact(
        StatementType.INCOME_STATEMENT,
        "20.0",
        p_curr_dur,
        CanonicalConcept.INCOME_TAX_EXPENSE,
    )

    s_bs_24 = make_statement(
        StatementType.BALANCE_SHEET, p_curr_dur, [f_debt_24, f_eq_24, f_cash_24]
    )
    s_is_24 = make_statement(
        StatementType.INCOME_STATEMENT, p_curr_dur, [f_ebit, f_ebt, f_tax]
    )
    store = MultiPeriodFactStore([s_bs_24, s_is_24])

    res = ROICEngine.calculate_roic(
        p_curr_dur, None, store, allow_point_in_time_fallback=True
    )
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.NON_POSITIVE_INVESTED_CAPITAL for d in res.diagnostics
    )
