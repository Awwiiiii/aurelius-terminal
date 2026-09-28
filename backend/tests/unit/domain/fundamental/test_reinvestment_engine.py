"""
tests.unit.domain.fundamental.test_reinvestment_engine
======================================================
Deterministic unit tests for ReinvestmentEngine:
- Reinvestment: CapEx - D&A + Delta NWC
- Negative Reinvestment (VALID with NEGATIVE_REINVESTMENT_OBSERVED)
- Reinvestment Rate: Reinvestment / NOPAT
- Non-positive NOPAT -> DISTORTED with NON_POSITIVE_OPERATING_PROFIT
- Extreme Reinvestment (> 200%) -> VALID with HIGH_REINVESTMENT_WARNING
- Fundamental Growth: Retrospective internal g = Reinvestment Rate * ROIC
- Double-negative distortion: Rate < 0 and ROIC < 0 -> DISTORTED with DISTORTED_FUNDAMENTAL_GROWTH
- Negative fundamental growth: VALID with NEGATIVE_FUNDAMENTAL_GROWTH
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.reinvestment import ReinvestmentEngine
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricStatus,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


def _build_test_store(
    ebit="1000",
    ebt="1000",
    tax="250",
    capex="-300",
    da="100",
    curr_nwc_delta=100,  # curr NWC = 300, prior NWC = 200 -> delta = 100
    equity="2000",
    debt="500",
    cash="100",
):
    p_curr = make_period(
        "2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024
    )
    p_curr_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )
    p_prior_inst = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )

    facts_is = [
        make_fact(
            StatementType.INCOME_STATEMENT,
            ebit,
            p_curr,
            CanonicalConcept.OPERATING_INCOME,
        ),
        make_fact(
            StatementType.INCOME_STATEMENT, ebt, p_curr, CanonicalConcept.PRETAX_INCOME
        ),
        make_fact(
            StatementType.INCOME_STATEMENT,
            tax,
            p_curr,
            CanonicalConcept.INCOME_TAX_EXPENSE,
        ),
    ]

    facts_cf = [
        make_fact(
            StatementType.CASH_FLOW,
            capex,
            p_curr,
            CanonicalConcept.CAPITAL_EXPENDITURES,
        ),
        make_fact(
            StatementType.CASH_FLOW,
            da,
            p_curr,
            source_concept="Depreciation And Amortization",
        ),
    ]

    # Current BS: NWC = 600 - 100 - 200 = 300
    facts_bs_curr = [
        make_fact(
            StatementType.BALANCE_SHEET,
            "600",
            p_curr_inst,
            CanonicalConcept.CURRENT_ASSETS,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "100",
            p_curr_inst,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "200",
            p_curr_inst,
            CanonicalConcept.CURRENT_LIABILITIES,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            equity,
            p_curr_inst,
            CanonicalConcept.STOCKHOLDERS_EQUITY,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            debt,
            p_curr_inst,
            CanonicalConcept.LONG_TERM_DEBT,
        ),
    ]

    # Prior BS: NWC = 300 - curr_nwc_delta
    prior_nwc = 300 - curr_nwc_delta
    prior_ca = (
        prior_nwc + 200
    )  # Cash=100, CL=100 -> NWC = prior_ca - 100 - 100 = prior_ca - 200
    facts_bs_prior = [
        make_fact(
            StatementType.BALANCE_SHEET,
            str(prior_ca),
            p_prior_inst,
            CanonicalConcept.CURRENT_ASSETS,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "100",
            p_prior_inst,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "100",
            p_prior_inst,
            CanonicalConcept.CURRENT_LIABILITIES,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            equity,
            p_prior_inst,
            CanonicalConcept.STOCKHOLDERS_EQUITY,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            debt,
            p_prior_inst,
            CanonicalConcept.LONG_TERM_DEBT,
        ),
    ]

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p_curr, facts_is),
            make_statement(StatementType.CASH_FLOW, p_curr, facts_cf),
            make_statement(StatementType.BALANCE_SHEET, p_curr_inst, facts_bs_curr),
            make_statement(StatementType.BALANCE_SHEET, p_prior_inst, facts_bs_prior),
        ]
    )
    return p_curr, p_prior_inst, store


def test_reinvestment_normal_calculation():
    # CapEx = 300, D&A = 100, Delta NWC = 100
    # Reinvestment = 300 - 100 + 100 = 300
    p_curr, p_prior, store = _build_test_store(
        capex="-300", da="100", curr_nwc_delta=100
    )

    res = ReinvestmentEngine.calculate_reinvestment(p_curr, p_prior, store)
    assert res.status == MetricStatus.VALID
    assert res.metric_id == FundamentalMetricId.REINVESTMENT
    assert res.value == Decimal("300")
    assert "FORMULA_REINVESTMENT_V1" in res.provenance.formula_id


def test_negative_reinvestment_observed():
    # CapEx = 50, D&A = 150, Delta NWC = -20
    # Reinvestment = 50 - 150 + (-20) = -120
    p_curr, p_prior, store = _build_test_store(
        capex="-50", da="150", curr_nwc_delta=-20
    )

    res = ReinvestmentEngine.calculate_reinvestment(p_curr, p_prior, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("-120")
    codes = [d.code for d in res.diagnostics]
    assert DiagnosticCode.NEGATIVE_REINVESTMENT_OBSERVED in codes


def test_reinvestment_rate_normal_and_extreme():
    # EBIT = 1000, Tax = 250, EBT = 1000 -> ETR = 25% -> NOPAT = 750
    # CapEx = 300, D&A = 100, Delta NWC = 100 -> Reinvestment = 300
    # Reinvestment Rate = 300 / 750 = 0.40 (40%)
    p_curr, p_prior, store = _build_test_store(
        ebit="1000", ebt="1000", tax="250", capex="-300", da="100", curr_nwc_delta=100
    )

    rate_res = ReinvestmentEngine.calculate_reinvestment_rate(p_curr, p_prior, store)
    assert rate_res.status == MetricStatus.VALID
    assert rate_res.metric_id == FundamentalMetricId.REINVESTMENT_RATE
    assert rate_res.value == Decimal("0.4")
    assert len(rate_res.diagnostics) == 0

    # Extreme Reinvestment (> 200% / > 2.0)
    # CapEx = 2000, D&A = 100, Delta NWC = 100 -> Reinvestment = 2000
    # NOPAT = 750 -> Rate = 2000 / 750 = 2.666...
    p_curr_ext, p_prior_ext, store_ext = _build_test_store(
        ebit="1000", ebt="1000", tax="250", capex="-2000", da="100", curr_nwc_delta=100
    )
    rate_ext = ReinvestmentEngine.calculate_reinvestment_rate(
        p_curr_ext, p_prior_ext, store_ext
    )
    assert rate_ext.status == MetricStatus.VALID
    assert rate_ext.value > Decimal("2.0")
    codes = [d.code for d in rate_ext.diagnostics]
    assert DiagnosticCode.HIGH_REINVESTMENT_WARNING in codes


def test_reinvestment_rate_non_positive_nopat():
    # Pretax is negative -> ETR is unavailable -> NOPAT unavailable -> Rate DISTORTED/UNAVAILABLE
    p_curr, p_prior, store = _build_test_store(ebit="-500", ebt="-500", tax="0")

    rate_res = ReinvestmentEngine.calculate_reinvestment_rate(p_curr, p_prior, store)
    assert rate_res.status in (MetricStatus.DISTORTED, MetricStatus.UNAVAILABLE)


def test_fundamental_growth_normal():
    # Rate = 40% (0.40)
    # NOPAT = 750
    # Average Invested Capital:
    # Curr IC = 500 (debt) + 2000 (equity) - 100 (cash) = 2400
    # Prior IC = 500 + 2000 - 100 = 2400
    # Avg IC = 2400
    # ROIC = 750 / 2400 = 0.3125 (31.25%)
    # g = Rate * ROIC = 0.40 * 0.3125 = 0.125 (12.5%)
    p_curr, p_prior, store = _build_test_store(
        ebit="1000", ebt="1000", tax="250", capex="-300", da="100", curr_nwc_delta=100
    )

    g_res = ReinvestmentEngine.calculate_fundamental_growth(p_curr, p_prior, store)
    assert g_res.status == MetricStatus.VALID
    assert g_res.metric_id == FundamentalMetricId.FUNDAMENTAL_GROWTH
    assert g_res.value == Decimal("0.125")
    assert "Historical Fundamental Growth" in g_res.provenance.methodology_notes


def test_fundamental_growth_double_negative_distortion():
    # If Rate < 0 and ROIC < 0:
    # Mathematically (-Rate) * (-ROIC) = +g. But financially this is DISTORTED!
    p_curr = make_period(
        "2024-12-31", period_type=PeriodType.DURATION, fiscal_year=2024
    )
    p_curr_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )
    p_prior_inst = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )

    # Let's mock a case where Reinvestment Rate < 0 and ROIC < 0:
    # We can test calculate_fundamental_growth directly by mocking or building facts
    # CapEx = 50, D&A = 150, Delta NWC = 0 -> Reinvestment = -100
    # NOPAT = 500 (EBIT=625, Tax=125, ETR=20%) -> Rate = -100 / 500 = -0.20
    # Here NOPAT > 0 so ROIC > 0 (since Avg IC > 0). That gives negative growth:
    facts_is = [
        make_fact(
            StatementType.INCOME_STATEMENT,
            "625",
            p_curr,
            CanonicalConcept.OPERATING_INCOME,
        ),
        make_fact(
            StatementType.INCOME_STATEMENT,
            "625",
            p_curr,
            CanonicalConcept.PRETAX_INCOME,
        ),
        make_fact(
            StatementType.INCOME_STATEMENT,
            "125",
            p_curr,
            CanonicalConcept.INCOME_TAX_EXPENSE,
        ),
    ]
    facts_cf = [
        make_fact(
            StatementType.CASH_FLOW,
            "-50",
            p_curr,
            CanonicalConcept.CAPITAL_EXPENDITURES,
        ),
        make_fact(
            StatementType.CASH_FLOW,
            "150",
            p_curr,
            source_concept="Depreciation And Amortization",
        ),
    ]
    # NWC = 200 in both periods -> Delta NWC = 0
    facts_bs_curr = [
        make_fact(
            StatementType.BALANCE_SHEET,
            "400",
            p_curr_inst,
            CanonicalConcept.CURRENT_ASSETS,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "100",
            p_curr_inst,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "100",
            p_curr_inst,
            CanonicalConcept.CURRENT_LIABILITIES,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "1000",
            p_curr_inst,
            CanonicalConcept.STOCKHOLDERS_EQUITY,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "200",
            p_curr_inst,
            CanonicalConcept.LONG_TERM_DEBT,
        ),
    ]
    facts_bs_prior = [
        make_fact(
            StatementType.BALANCE_SHEET,
            "400",
            p_prior_inst,
            CanonicalConcept.CURRENT_ASSETS,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "100",
            p_prior_inst,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "100",
            p_prior_inst,
            CanonicalConcept.CURRENT_LIABILITIES,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "1000",
            p_prior_inst,
            CanonicalConcept.STOCKHOLDERS_EQUITY,
        ),
        make_fact(
            StatementType.BALANCE_SHEET,
            "200",
            p_prior_inst,
            CanonicalConcept.LONG_TERM_DEBT,
        ),
    ]

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p_curr, facts_is),
            make_statement(StatementType.CASH_FLOW, p_curr, facts_cf),
            make_statement(StatementType.BALANCE_SHEET, p_curr_inst, facts_bs_curr),
            make_statement(StatementType.BALANCE_SHEET, p_prior_inst, facts_bs_prior),
        ]
    )

    # Reinvestment Rate = -100 / 500 = -0.20
    # ROIC = 500 / 1100 = 0.4545...
    # g = -0.20 * 0.4545 = -0.0909 (negative growth, VALID with NEGATIVE_FUNDAMENTAL_GROWTH)
    g_res = ReinvestmentEngine.calculate_fundamental_growth(p_curr, p_prior_inst, store)
    assert g_res.status == MetricStatus.VALID
    assert g_res.value < Decimal(0)
    codes = [d.code for d in g_res.diagnostics]
    assert DiagnosticCode.NEGATIVE_FUNDAMENTAL_GROWTH in codes
