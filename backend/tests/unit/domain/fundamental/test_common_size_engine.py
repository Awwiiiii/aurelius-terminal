"""
tests.unit.domain.fundamental.test_common_size_engine
======================================================
Unit tests for Common-Size Income Statement, Balance Sheet, and Cash Flow Statement.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodLabel,
    FiscalPeriodType,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.common_size import CommonSizeEngine
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    MetricStatus,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore
from aurelius.domain.fundamental.ttm import TTMEngine
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


def test_common_size_income_statement_normal():
    period = make_period("2024-12-31")
    f_rev = make_fact(
        StatementType.INCOME_STATEMENT, "1000.0", period, CanonicalConcept.REVENUE
    )
    f_cogs = make_fact(
        StatementType.INCOME_STATEMENT,
        "400.0",
        period,
        CanonicalConcept.COST_OF_REVENUE,
    )
    f_gp = make_fact(
        StatementType.INCOME_STATEMENT, "600.0", period, CanonicalConcept.GROSS_PROFIT
    )
    f_ni = make_fact(
        StatementType.INCOME_STATEMENT, "150.0", period, CanonicalConcept.NET_INCOME
    )

    stmt = make_statement(
        StatementType.INCOME_STATEMENT, period, [f_rev, f_cogs, f_gp, f_ni]
    )
    store = MultiPeriodFactStore([stmt])

    res = CommonSizeEngine.calculate_common_size_income_statement(period, store)
    assert res.status == MetricStatus.VALID
    assert res.base_value == Decimal("1000.0")

    items_dict = {i.concept_name: i.common_size_percent for i in res.items}
    assert items_dict["REVENUE"] == Decimal("100.0")
    assert items_dict["COST_OF_REVENUE"] == Decimal("40.0")
    assert items_dict["GROSS_PROFIT"] == Decimal("60.0")
    assert items_dict["NET_INCOME"] == Decimal("15.0")


def test_common_size_balance_sheet_normal():
    period = make_period("2024-12-31", period_type=PeriodType.INSTANT)
    f_assets = make_fact(
        StatementType.BALANCE_SHEET, "2000.0", period, CanonicalConcept.TOTAL_ASSETS
    )
    f_cash = make_fact(
        StatementType.BALANCE_SHEET,
        "500.0",
        period,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
    )
    f_debt = make_fact(
        StatementType.BALANCE_SHEET, "600.0", period, CanonicalConcept.LONG_TERM_DEBT
    )

    stmt = make_statement(
        StatementType.BALANCE_SHEET, period, [f_assets, f_cash, f_debt]
    )
    store = MultiPeriodFactStore([stmt])

    res = CommonSizeEngine.calculate_common_size_balance_sheet(period, store)
    assert res.status == MetricStatus.VALID
    assert res.base_value == Decimal("2000.0")

    items_dict = {i.concept_name: i.common_size_percent for i in res.items}
    assert items_dict["TOTAL_ASSETS"] == Decimal("100.0")
    assert items_dict["CASH_AND_EQUIVALENTS"] == Decimal("25.0")
    assert items_dict["LONG_TERM_DEBT"] == Decimal("30.0")


def test_common_size_cash_flow_capex_sign_magnitude():
    period = make_period("2024-12-31")
    f_rev = make_fact(
        StatementType.INCOME_STATEMENT, "1000.0", period, CanonicalConcept.REVENUE
    )
    f_cfo = make_fact(
        StatementType.CASH_FLOW, "250.0", period, CanonicalConcept.OPERATING_CASH_FLOW
    )
    # Negative reported CapEx outflow
    f_capex = make_fact(
        StatementType.CASH_FLOW, "-100.0", period, CanonicalConcept.CAPITAL_EXPENDITURES
    )

    s_is = make_statement(StatementType.INCOME_STATEMENT, period, [f_rev])
    s_cf = make_statement(StatementType.CASH_FLOW, period, [f_cfo, f_capex])
    store = MultiPeriodFactStore([s_is, s_cf])

    res = CommonSizeEngine.calculate_common_size_cash_flow(period, store)
    assert res.status == MetricStatus.VALID

    items_dict = {
        i.concept_name: (i.reported_value, i.common_size_percent) for i in res.items
    }
    # CFO: 250 / 1000 = 25%
    assert items_dict["OPERATING_CASH_FLOW"] == (Decimal("250.0"), Decimal("25.0"))
    # CapEx: Normalized to positive economic magnitude 100 / 1000 = 10%
    assert items_dict["CAPITAL_EXPENDITURES"] == (Decimal("100.0"), Decimal("10.0"))
    # FCF: CFO (250) - abs(CapEx) (100) = 150 / 1000 = 15%
    assert items_dict["FREE_CASH_FLOW"] == (Decimal("150.0"), Decimal("15.0"))


def test_common_size_non_positive_denominators():
    period = make_period("2024-12-31")
    f_rev_zero = make_fact(
        StatementType.INCOME_STATEMENT, "0.0", period, CanonicalConcept.REVENUE
    )
    s_is = make_statement(StatementType.INCOME_STATEMENT, period, [f_rev_zero])
    store = MultiPeriodFactStore([s_is])

    res_is = CommonSizeEngine.calculate_common_size_income_statement(period, store)
    assert res_is.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.NON_POSITIVE_BASE_REVENUE for d in res_is.diagnostics
    )

    res_cf = CommonSizeEngine.calculate_common_size_cash_flow(period, store)
    assert res_cf.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.NON_POSITIVE_BASE_REVENUE for d in res_cf.diagnostics
    )


def test_common_size_ttm_statements():
    q1 = make_period("2024-03-31", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q1)
    q2 = make_period("2024-06-30", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q2)
    q3 = make_period("2024-09-30", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q3)
    q4 = make_period("2024-12-31", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q4)

    stmts = []
    for q, rev_val in [(q1, "250.0"), (q2, "250.0"), (q3, "250.0"), (q4, "250.0")]:
        f_rev = make_fact(
            StatementType.INCOME_STATEMENT, rev_val, q, CanonicalConcept.REVENUE
        )
        f_ni = make_fact(
            StatementType.INCOME_STATEMENT, "25.0", q, CanonicalConcept.NET_INCOME
        )
        f_cfo = make_fact(
            StatementType.CASH_FLOW, "50.0", q, CanonicalConcept.OPERATING_CASH_FLOW
        )
        f_capex = make_fact(
            StatementType.CASH_FLOW, "-10.0", q, CanonicalConcept.CAPITAL_EXPENDITURES
        )

        s_is = make_statement(
            StatementType.INCOME_STATEMENT,
            q,
            [f_rev, f_ni],
            frequency=FiscalPeriodType.QUARTERLY,
        )
        s_cf = make_statement(
            StatementType.CASH_FLOW,
            q,
            [f_cfo, f_capex],
            frequency=FiscalPeriodType.QUARTERLY,
        )
        stmts.extend([s_is, s_cf])

    store = MultiPeriodFactStore(stmts)
    window, diag = TTMEngine.resolve_ttm_window(q4, [q1, q2, q3, q4])
    assert window is not None

    res_is_ttm = CommonSizeEngine.calculate_common_size_ttm_income_statement(
        window, store
    )
    assert res_is_ttm.status == MetricStatus.VALID
    assert res_is_ttm.base_value == Decimal("1000.0")  # 4 * 250
    items_dict = {i.concept_name: i.common_size_percent for i in res_is_ttm.items}
    assert items_dict["REVENUE"] == Decimal("100.0")
    assert items_dict["NET_INCOME"] == Decimal("10.0")  # (4 * 25) / 1000

    res_cf_ttm = CommonSizeEngine.calculate_common_size_ttm_cash_flow(window, store)
    assert res_cf_ttm.status == MetricStatus.VALID
    items_cf = {i.concept_name: i.common_size_percent for i in res_cf_ttm.items}
    assert items_cf["OPERATING_CASH_FLOW"] == Decimal("20.0")  # (4 * 50) / 1000
    assert items_cf["CAPITAL_EXPENDITURES"] == Decimal("4.0")  # (4 * 10) / 1000
    assert items_cf["FREE_CASH_FLOW"] == Decimal("16.0")  # 20 - 4
