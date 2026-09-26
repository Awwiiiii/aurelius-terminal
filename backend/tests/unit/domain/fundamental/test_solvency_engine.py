"""
tests.unit.domain.fundamental.test_solvency_engine
==================================================
Deterministic tests for SolvencyEngine: Canonical Gross Debt hierarchy,
Net Debt, Debt-to-Equity negative equity handling, Interest Coverage with negative EBIT,
and reported EBITDA leverage restrictions.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.solvency import SolvencyEngine
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


def test_gross_debt_hierarchy_st_plus_lt():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_lt = make_fact(
        StatementType.BALANCE_SHEET,
        "800",
        p,
        CanonicalConcept.LONG_TERM_DEBT,
        "Long Term Debt",
    )
    fact_st = make_fact(StatementType.BALANCE_SHEET, "200", p, None, "Current Debt")

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_lt, fact_st])]
    )

    val, facts, formula_id, notes, diag = SolvencyEngine.resolve_gross_debt(p, store)
    assert val == Decimal("1000")
    assert formula_id == "FORMULA_GROSS_DEBT_ST_PLUS_LT"
    assert len(facts) == 2
    assert diag is None


def test_gross_debt_hierarchy_reported_total():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_total = make_fact(StatementType.BALANCE_SHEET, "950", p, None, "Total Debt")

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_total])]
    )

    val, facts, formula_id, notes, diag = SolvencyEngine.resolve_gross_debt(p, store)
    assert val == Decimal("950")
    assert formula_id == "FORMULA_GROSS_DEBT_REPORTED_TOTAL"
    assert len(facts) == 1
    assert diag is None


def test_gross_debt_hierarchy_lt_only_with_warning():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_lt = make_fact(
        StatementType.BALANCE_SHEET,
        "700",
        p,
        CanonicalConcept.LONG_TERM_DEBT,
        "Long Term Debt",
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_lt])]
    )

    val, facts, formula_id, notes, diag = SolvencyEngine.resolve_gross_debt(p, store)
    assert val == Decimal("700")
    assert formula_id == "FORMULA_GROSS_DEBT_LT_ONLY"
    assert diag is not None
    assert diag.code == DiagnosticCode.SHORT_TERM_DEBT_UNAVAILABLE


def test_net_debt_negative_net_cash_valid():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_lt = make_fact(
        StatementType.BALANCE_SHEET,
        "300",
        p,
        CanonicalConcept.LONG_TERM_DEBT,
        "Long Term Debt",
    )
    fact_cash = make_fact(
        StatementType.BALANCE_SHEET, "500", p, CanonicalConcept.CASH_AND_EQUIVALENTS
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_lt, fact_cash])]
    )

    res = SolvencyEngine.calculate_net_debt(p, store)
    assert res.status == MetricStatus.VALID
    # Net Debt = 300 - 500 = -200 (Net cash position)
    assert res.value == Decimal("-200")


def test_debt_to_equity_negative_equity_distorted():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_lt = make_fact(
        StatementType.BALANCE_SHEET,
        "1000",
        p,
        CanonicalConcept.LONG_TERM_DEBT,
        "Long Term Debt",
    )
    fact_eq = make_fact(
        StatementType.BALANCE_SHEET, "-150", p, CanonicalConcept.STOCKHOLDERS_EQUITY
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_lt, fact_eq])]
    )

    res = SolvencyEngine.calculate_debt_to_equity(p, store)
    assert res.status == MetricStatus.DISTORTED
    assert res.value is None
    assert any(
        d.code == DiagnosticCode.NEGATIVE_OR_ZERO_EQUITY for d in res.diagnostics
    )


def test_interest_coverage_negative_ebit_warning():
    p = make_period("2024-12-31")
    fact_ebit = make_fact(
        StatementType.INCOME_STATEMENT, "-100", p, CanonicalConcept.OPERATING_INCOME
    )
    fact_int = make_fact(
        StatementType.INCOME_STATEMENT, "50", p, None, "Interest Expense"
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.INCOME_STATEMENT, p, [fact_ebit, fact_int])]
    )

    res = SolvencyEngine.calculate_interest_coverage(p, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("-2")
    assert res.formatted_value == "-2.00x"
    assert any(d.code == DiagnosticCode.NEGATIVE_EBIT_WARNING for d in res.diagnostics)


def test_interest_coverage_zero_interest():
    p = make_period("2024-12-31")
    fact_ebit = make_fact(
        StatementType.INCOME_STATEMENT, "300", p, CanonicalConcept.OPERATING_INCOME
    )
    fact_int = make_fact(
        StatementType.INCOME_STATEMENT, "0", p, None, "Interest Expense"
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.INCOME_STATEMENT, p, [fact_ebit, fact_int])]
    )

    res = SolvencyEngine.calculate_interest_coverage(p, store)
    assert res.status == MetricStatus.DISTORTED
    assert any(d.code == DiagnosticCode.ZERO_INTEREST_EXPENSE for d in res.diagnostics)


def test_debt_to_ebitda_requires_reported_ebitda():
    p_inst = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_debt = make_fact(
        StatementType.BALANCE_SHEET,
        "1000",
        p_inst,
        CanonicalConcept.LONG_TERM_DEBT,
        "Long Term Debt",
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p_inst, [fact_debt])]
    )

    res = SolvencyEngine.calculate_debt_to_ebitda(p_inst, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.NON_REPORTED_EBITDA_RESTRICTION
        for d in res.diagnostics
    )


def test_debt_to_ebitda_negative_ebitda_distorted():
    p_inst = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_debt = make_fact(
        StatementType.BALANCE_SHEET,
        "1000",
        p_inst,
        CanonicalConcept.LONG_TERM_DEBT,
        "Long Term Debt",
    )
    fact_ebitda = make_fact(
        StatementType.INCOME_STATEMENT, "-200", p_inst, CanonicalConcept.EBITDA
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.BALANCE_SHEET, p_inst, [fact_debt]),
            make_statement(StatementType.INCOME_STATEMENT, p_inst, [fact_ebitda]),
        ]
    )

    res = SolvencyEngine.calculate_debt_to_ebitda(p_inst, store)
    assert res.status == MetricStatus.DISTORTED
    assert any(
        d.code == DiagnosticCode.NEGATIVE_OR_ZERO_EBITDA for d in res.diagnostics
    )


def test_gross_debt_hierarchy_st_only_with_warning():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_st = make_fact(StatementType.BALANCE_SHEET, "450", p, None, "Current Debt")

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_st])]
    )

    val, facts, formula_id, notes, diag = SolvencyEngine.resolve_gross_debt(p, store)
    assert val == Decimal("450")
    assert formula_id == "FORMULA_GROSS_DEBT_ST_ONLY"
    assert len(facts) == 1
    assert diag is not None
    assert diag.code == DiagnosticCode.LONG_TERM_DEBT_UNAVAILABLE


def test_gross_debt_hierarchy_neither_available():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    # Only accounts payable and cash, no funded debt
    fact_ap = make_fact(
        StatementType.BALANCE_SHEET, "300", p, CanonicalConcept.ACCOUNTS_PAYABLE
    )
    fact_cash = make_fact(
        StatementType.BALANCE_SHEET, "500", p, CanonicalConcept.CASH_AND_EQUIVALENTS
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_ap, fact_cash])]
    )

    val, facts, formula_id, notes, diag = SolvencyEngine.resolve_gross_debt(p, store)
    assert val is None
    assert facts == []
    assert diag is not None
    assert diag.code == DiagnosticCode.MISSING_REQUIRED_FACT


def test_gross_debt_does_not_treat_current_liabilities_as_debt():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    fact_ap = make_fact(
        StatementType.BALANCE_SHEET, "200", p, CanonicalConcept.ACCOUNTS_PAYABLE
    )
    fact_cl = make_fact(
        StatementType.BALANCE_SHEET, "1500", p, None, "Other Current Liabilities"
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_ap, fact_cl])]
    )

    val, facts, formula_id, notes, diag = SolvencyEngine.resolve_gross_debt(p, store)
    assert val is None
    assert diag is not None
    assert diag.code == DiagnosticCode.MISSING_REQUIRED_FACT


def test_interest_coverage_positive_interest():
    p = make_period("2024-12-31")
    fact_ebit = make_fact(
        StatementType.INCOME_STATEMENT, "500", p, CanonicalConcept.OPERATING_INCOME
    )
    fact_int = make_fact(
        StatementType.INCOME_STATEMENT, "100", p, None, "Interest Expense"
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.INCOME_STATEMENT, p, [fact_ebit, fact_int])]
    )

    res = SolvencyEngine.calculate_interest_coverage(p, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("5")
    assert res.formatted_value == "5.00x"
    assert res.provenance.formula_id == "FORMULA_INTEREST_COVERAGE"
    assert not any(
        d.code == DiagnosticCode.INVALID_INTEREST_SIGN for d in res.diagnostics
    )


def test_interest_coverage_negative_interest_sign_distorted():
    p = make_period("2024-12-31")
    fact_ebit = make_fact(
        StatementType.INCOME_STATEMENT, "500", p, CanonicalConcept.OPERATING_INCOME
    )
    # Negative interest expense representing net interest income or negative sign convention
    fact_int = make_fact(
        StatementType.INCOME_STATEMENT, "-50", p, None, "Interest Expense"
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.INCOME_STATEMENT, p, [fact_ebit, fact_int])]
    )

    res = SolvencyEngine.calculate_interest_coverage(p, store)
    assert res.status == MetricStatus.DISTORTED
    assert res.value is None
    assert any(d.code == DiagnosticCode.INVALID_INTEREST_SIGN for d in res.diagnostics)
