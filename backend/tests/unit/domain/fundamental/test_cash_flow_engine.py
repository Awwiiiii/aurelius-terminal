"""
tests.unit.domain.fundamental.test_cash_flow_engine
===================================================
Deterministic tests for CashFlowEngine: CFO, CapEx source sign normalization,
AURELIUS Primary FCF, FCF Margin, and FCF / CFO Conversion with zero/negative Net Income.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    StatementType,
)
from aurelius.domain.fundamental.engines.cash_flow import CashFlowEngine
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


def test_capex_sign_normalization_identical_fcf():
    p = make_period("2024-12-31")

    # CFO = 1200
    fact_cfo = make_fact(
        StatementType.CASH_FLOW, "1200", p, CanonicalConcept.OPERATING_CASH_FLOW
    )

    # Case A: CapEx reported negative (-500)
    fact_capex_neg = make_fact(
        StatementType.CASH_FLOW, "-500", p, CanonicalConcept.CAPITAL_EXPENDITURES
    )
    store_neg = MultiPeriodFactStore(
        [make_statement(StatementType.CASH_FLOW, p, [fact_cfo, fact_capex_neg])]
    )

    # Case B: CapEx reported positive (+500)
    fact_capex_pos = make_fact(
        StatementType.CASH_FLOW, "500", p, CanonicalConcept.CAPITAL_EXPENDITURES
    )
    store_pos = MultiPeriodFactStore(
        [make_statement(StatementType.CASH_FLOW, p, [fact_cfo, fact_capex_pos])]
    )

    fcf_res_neg = CashFlowEngine.calculate_free_cash_flow(p, store_neg)
    fcf_res_pos = CashFlowEngine.calculate_free_cash_flow(p, store_pos)

    # Both must produce identical FCF = 1200 - 500 = 700
    assert fcf_res_neg.status == MetricStatus.VALID
    assert fcf_res_pos.status == MetricStatus.VALID
    assert fcf_res_neg.value == Decimal("700")
    assert fcf_res_pos.value == Decimal("700")
    assert fcf_res_neg.provenance.formula_id == "FORMULA_AURELIUS_PRIMARY_FCF"
    assert "AURELIUS canonical primary FCF convention" in (
        fcf_res_neg.provenance.methodology_notes or ""
    )


def test_fcf_conversion_zero_net_income():
    p = make_period("2024-12-31")
    fact_cfo = make_fact(
        StatementType.CASH_FLOW, "1200", p, CanonicalConcept.OPERATING_CASH_FLOW
    )
    fact_capex = make_fact(
        StatementType.CASH_FLOW, "400", p, CanonicalConcept.CAPITAL_EXPENDITURES
    )
    fact_ni = make_fact(
        StatementType.INCOME_STATEMENT, "0", p, CanonicalConcept.NET_INCOME
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.CASH_FLOW, p, [fact_cfo, fact_capex]),
            make_statement(StatementType.INCOME_STATEMENT, p, [fact_ni]),
        ]
    )

    res = CashFlowEngine.calculate_fcf_conversion(p, store)
    assert res.status == MetricStatus.DISTORTED
    assert res.value is None
    assert any(d.code == DiagnosticCode.ZERO_DIVISION for d in res.diagnostics)


def test_fcf_conversion_negative_net_income():
    p = make_period("2024-12-31")
    fact_cfo = make_fact(
        StatementType.CASH_FLOW, "800", p, CanonicalConcept.OPERATING_CASH_FLOW
    )
    fact_capex = make_fact(
        StatementType.CASH_FLOW, "300", p, CanonicalConcept.CAPITAL_EXPENDITURES
    )
    fact_ni = make_fact(
        StatementType.INCOME_STATEMENT, "-150", p, CanonicalConcept.NET_INCOME
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.CASH_FLOW, p, [fact_cfo, fact_capex]),
            make_statement(StatementType.INCOME_STATEMENT, p, [fact_ni]),
        ]
    )

    res = CashFlowEngine.calculate_fcf_conversion(p, store)
    assert res.status == MetricStatus.DISTORTED
    assert res.value is None
    assert any(d.code == DiagnosticCode.NEGATIVE_NET_INCOME for d in res.diagnostics)


def test_cfo_to_net_income_normal():
    p = make_period("2024-12-31")
    fact_cfo = make_fact(
        StatementType.CASH_FLOW, "1200", p, CanonicalConcept.OPERATING_CASH_FLOW
    )
    fact_ni = make_fact(
        StatementType.INCOME_STATEMENT, "1000", p, CanonicalConcept.NET_INCOME
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.CASH_FLOW, p, [fact_cfo]),
            make_statement(StatementType.INCOME_STATEMENT, p, [fact_ni]),
        ]
    )

    res = CashFlowEngine.calculate_cfo_to_net_income(p, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("1.2")
    assert res.formatted_value == "1.20x"
