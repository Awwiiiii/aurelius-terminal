"""
tests.unit.domain.fundamental.test_capital_allocation_engine
=============================================================
Deterministic unit tests for CapitalAllocationEngine:
- Operating Cash Flow (CFO)
- CapEx magnitude normalization
- Dividends paid (magnitude normalization, non-payer zero evaluation)
- Stock repurchases and stock issuances
- Gross and net debt flows
- M&A investment (missing -> M_AND_A_DATA_UNAVAILABLE)
- Shareholder yields: Dividend, Buyback, Gross Shareholder, Net Shareholder Yield
- Non-positive and missing market cap handling
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.capital_allocation import (
    CapitalAllocationEngine,
)
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


def test_capital_allocation_flows_normal():
    p = make_period("2024-12-31", period_type=PeriodType.DURATION)

    # CFO = 1000
    fact_cfo = make_fact(
        StatementType.CASH_FLOW, "1000", p, CanonicalConcept.OPERATING_CASH_FLOW
    )
    # CapEx reported as -300
    fact_capex = make_fact(
        StatementType.CASH_FLOW, "-300", p, CanonicalConcept.CAPITAL_EXPENDITURES
    )
    # Dividends paid reported as -100
    fact_div = make_fact(
        StatementType.CASH_FLOW, "-100", p, source_concept="Cash Dividends Paid"
    )
    # Repurchases reported as -200
    fact_rep = make_fact(
        StatementType.CASH_FLOW, "-200", p, source_concept="Repurchase Of Capital Stock"
    )
    # Issuance reported as 50
    fact_iss = make_fact(
        StatementType.CASH_FLOW, "50", p, source_concept="Issuance Of Capital Stock"
    )
    # Debt issued = 400, Debt repaid = -250
    fact_d_iss = make_fact(
        StatementType.CASH_FLOW, "400", p, source_concept="Issuance Of Debt"
    )
    fact_d_rep = make_fact(
        StatementType.CASH_FLOW, "-250", p, source_concept="Repayment Of Debt"
    )
    # M&A = -80
    fact_ma = make_fact(
        StatementType.CASH_FLOW, "-80", p, source_concept="Acquisition Of Business"
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.CASH_FLOW,
                p,
                [
                    fact_cfo,
                    fact_capex,
                    fact_div,
                    fact_rep,
                    fact_iss,
                    fact_d_iss,
                    fact_d_rep,
                    fact_ma,
                ],
            )
        ]
    )

    # CFO
    cfo_res = CapitalAllocationEngine.calculate_cfo(p, store)
    assert cfo_res.status == MetricStatus.VALID
    assert cfo_res.value == Decimal("1000")

    # CapEx normalized to positive 300
    capex_res = CapitalAllocationEngine.calculate_capex(p, store)
    assert capex_res.status == MetricStatus.VALID
    assert capex_res.value == Decimal("300")

    # Dividends Paid normalized to positive 100
    div_res = CapitalAllocationEngine.calculate_dividends_paid(p, store)
    assert div_res.status == MetricStatus.VALID
    assert div_res.value == Decimal("100")

    # Repurchases normalized to positive 200
    rep_res = CapitalAllocationEngine.calculate_stock_repurchases(p, store)
    assert rep_res.status == MetricStatus.VALID
    assert rep_res.value == Decimal("200")

    # Issuances = 50
    iss_res = CapitalAllocationEngine.calculate_stock_issuance(p, store)
    assert iss_res.status == MetricStatus.VALID
    assert iss_res.value == Decimal("50")

    # Debt Issued = 400, Repaid = 250, Net = 150
    d_iss_res = CapitalAllocationEngine.calculate_debt_issued(p, store)
    assert d_iss_res.status == MetricStatus.VALID
    assert d_iss_res.value == Decimal("400")

    d_rep_res = CapitalAllocationEngine.calculate_debt_repaid(p, store)
    assert d_rep_res.status == MetricStatus.VALID
    assert d_rep_res.value == Decimal("250")

    net_d_res = CapitalAllocationEngine.calculate_net_debt_issued(p, store)
    assert net_d_res.status == MetricStatus.VALID
    assert net_d_res.value == Decimal("150")

    # M&A normalized to positive 80
    ma_res = CapitalAllocationEngine.calculate_ma_investment(p, store)
    assert ma_res.status == MetricStatus.VALID
    assert ma_res.value == Decimal("80")


def test_capital_allocation_ma_omitted_diagnostic():
    p = make_period("2024-12-31", period_type=PeriodType.DURATION)
    fact_cfo = make_fact(
        StatementType.CASH_FLOW, "500", p, CanonicalConcept.OPERATING_CASH_FLOW
    )
    store = MultiPeriodFactStore(
        [make_statement(StatementType.CASH_FLOW, p, [fact_cfo])]
    )

    # M&A absent from cash flow statement -> UNAVAILABLE with M_AND_A_DATA_UNAVAILABLE
    ma_res = CapitalAllocationEngine.calculate_ma_investment(p, store)
    assert ma_res.status == MetricStatus.UNAVAILABLE
    codes = [d.code for d in ma_res.diagnostics]
    assert DiagnosticCode.M_AND_A_DATA_UNAVAILABLE in codes


def test_shareholder_yields_normal():
    p = make_period("2024-12-31", period_type=PeriodType.DURATION)
    # Dividends = 100, Repurchases = 200, Issuance = 50, Market Cap = 5000
    fact_div = make_fact(
        StatementType.CASH_FLOW, "100", p, source_concept="Cash Dividends Paid"
    )
    fact_rep = make_fact(
        StatementType.CASH_FLOW, "200", p, source_concept="Repurchase Of Capital Stock"
    )
    fact_iss = make_fact(
        StatementType.CASH_FLOW, "50", p, source_concept="Issuance Of Capital Stock"
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.CASH_FLOW, p, [fact_div, fact_rep, fact_iss])]
    )
    mcap = Decimal("5000")

    # Div Yield = 100 / 5000 = 0.02 (2.0%)
    dy = CapitalAllocationEngine.calculate_dividend_yield(p, store, mcap)
    assert dy.status == MetricStatus.VALID
    assert dy.value == Decimal("0.02")

    # Buyback Yield = 200 / 5000 = 0.04 (4.0%)
    by = CapitalAllocationEngine.calculate_buyback_yield(p, store, mcap)
    assert by.status == MetricStatus.VALID
    assert by.value == Decimal("0.04")

    # Gross Shareholder Yield = (100 + 200) / 5000 = 0.06 (6.0%)
    gsy = CapitalAllocationEngine.calculate_gross_shareholder_yield(p, store, mcap)
    assert gsy.status == MetricStatus.VALID
    assert gsy.value == Decimal("0.06")

    # Net Shareholder Yield = (100 + 200 - 50) / 5000 = 250 / 5000 = 0.05 (5.0%)
    nsy = CapitalAllocationEngine.calculate_net_shareholder_yield(p, store, mcap)
    assert nsy.status == MetricStatus.VALID
    assert nsy.value == Decimal("0.05")


def test_shareholder_yields_market_cap_boundaries():
    p = make_period("2024-12-31", period_type=PeriodType.DURATION)
    fact_div = make_fact(
        StatementType.CASH_FLOW, "100", p, source_concept="Cash Dividends Paid"
    )
    store = MultiPeriodFactStore(
        [make_statement(StatementType.CASH_FLOW, p, [fact_div])]
    )

    # None market cap -> UNAVAILABLE
    dy_none = CapitalAllocationEngine.calculate_dividend_yield(p, store, None)
    assert dy_none.status == MetricStatus.UNAVAILABLE
    codes_none = [d.code for d in dy_none.diagnostics]
    assert DiagnosticCode.MARKET_CAP_UNAVAILABLE in codes_none

    # Zero or negative market cap -> DISTORTED
    dy_zero = CapitalAllocationEngine.calculate_dividend_yield(p, store, Decimal("0"))
    assert dy_zero.status == MetricStatus.DISTORTED
    codes_zero = [d.code for d in dy_zero.diagnostics]
    assert DiagnosticCode.NON_POSITIVE_MARKET_CAP in codes_zero
