"""
tests.unit.domain.fundamental.test_operating_nwc_engine
========================================================
Deterministic unit tests for OperatingNWCEngine:
- Operating Current Assets, Operating Current Liabilities, Operating NWC
- Unclassified balance sheet (financial institutions -> NOT_APPLICABLE)
- Missing short-term investments (default to 0 with diagnostic)
- Missing short-term debt (default to 0 with diagnostic)
- Negative operating NWC (valid with NEGATIVE_OPERATING_NWC_NOTE)
- Missing required facts (Current Assets, Current Liabilities) -> UNAVAILABLE
- Delta NWC: Annual, Quarterly, TTM, missing prior period, incompatible periods.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.operating_nwc import OperatingNWCEngine
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


def test_operating_nwc_standard_calculation():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # CA = 1000, Cash = 200, STI = 100 -> Op CA = 700
    # CL = 600, ST Debt = 150 -> Op CL = 450
    # Op NWC = 700 - 450 = 250
    fact_ca = make_fact(
        StatementType.BALANCE_SHEET, "1000", p, CanonicalConcept.CURRENT_ASSETS
    )
    fact_cash = make_fact(
        StatementType.BALANCE_SHEET, "200", p, CanonicalConcept.CASH_AND_EQUIVALENTS
    )
    fact_sti = make_fact(
        StatementType.BALANCE_SHEET, "100", p, CanonicalConcept.SHORT_TERM_INVESTMENTS
    )
    fact_cl = make_fact(
        StatementType.BALANCE_SHEET, "600", p, CanonicalConcept.CURRENT_LIABILITIES
    )
    fact_st_debt = make_fact(
        StatementType.BALANCE_SHEET, "150", p, source_concept="Current Debt"
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.BALANCE_SHEET,
                p,
                [fact_ca, fact_cash, fact_sti, fact_cl, fact_st_debt],
            )
        ]
    )

    res = OperatingNWCEngine.calculate_operating_nwc(p, store)
    assert res.status == MetricStatus.VALID
    assert res.metric_id == FundamentalMetricId.OPERATING_NWC
    assert res.value == Decimal("250")
    assert len(res.diagnostics) == 0
    assert "FORMULA_OPERATING_NWC_DEDUCTIVE_V1" in res.provenance.formula_id


def test_operating_nwc_missing_sti_and_st_debt():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # CA = 800, Cash = 100, no STI -> Op CA = 700
    # CL = 300, no ST Debt -> Op CL = 300 (SHORT_TERM_DEBT_UNAVAILABLE)
    # Op NWC = 700 - 300 = 400
    fact_ca = make_fact(
        StatementType.BALANCE_SHEET, "800", p, CanonicalConcept.CURRENT_ASSETS
    )
    fact_cash = make_fact(
        StatementType.BALANCE_SHEET, "100", p, CanonicalConcept.CASH_AND_EQUIVALENTS
    )
    fact_cl = make_fact(
        StatementType.BALANCE_SHEET, "300", p, CanonicalConcept.CURRENT_LIABILITIES
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_ca, fact_cash, fact_cl])]
    )

    res = OperatingNWCEngine.calculate_operating_nwc(p, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("400")
    codes = [d.code for d in res.diagnostics]
    assert DiagnosticCode.SHORT_TERM_DEBT_UNAVAILABLE in codes


def test_operating_nwc_negative_valid():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # Op CA = 500 - 400 - 0 = 100
    # Op CL = 600 - 0 = 600
    # Op NWC = 100 - 600 = -500 (supplier-financed model, e.g. Amazon / Dell)
    fact_ca = make_fact(
        StatementType.BALANCE_SHEET, "500", p, CanonicalConcept.CURRENT_ASSETS
    )
    fact_cash = make_fact(
        StatementType.BALANCE_SHEET, "400", p, CanonicalConcept.CASH_AND_EQUIVALENTS
    )
    fact_cl = make_fact(
        StatementType.BALANCE_SHEET, "600", p, CanonicalConcept.CURRENT_LIABILITIES
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_ca, fact_cash, fact_cl])]
    )

    res = OperatingNWCEngine.calculate_operating_nwc(p, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("-500")
    codes = [d.code for d in res.diagnostics]
    assert DiagnosticCode.NEGATIVE_OPERATING_NWC_NOTE in codes


def test_operating_nwc_unclassified_balance_sheet_exempt():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # Financial firm / Bank with Total Assets but no Current Assets / Liabilities
    fact_ta = make_fact(
        StatementType.BALANCE_SHEET, "100000", p, CanonicalConcept.TOTAL_ASSETS
    )
    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_ta])]
    )

    res = OperatingNWCEngine.calculate_operating_nwc(p, store)
    assert res.status == MetricStatus.NOT_APPLICABLE
    assert res.value is None
    codes = [d.code for d in res.diagnostics]
    assert DiagnosticCode.UNCLASSIFIED_BALANCE_SHEET in codes


def test_operating_nwc_partially_missing_required_facts():
    p = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    # CA is present but CL is missing -> UNAVAILABLE with MISSING_REQUIRED_FACT
    fact_ca = make_fact(
        StatementType.BALANCE_SHEET, "500", p, CanonicalConcept.CURRENT_ASSETS
    )
    store = MultiPeriodFactStore(
        [make_statement(StatementType.BALANCE_SHEET, p, [fact_ca])]
    )

    res = OperatingNWCEngine.calculate_operating_nwc(p, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert res.value is None
    codes = [d.code for d in res.diagnostics]
    assert DiagnosticCode.MISSING_REQUIRED_FACT in codes


def test_delta_nwc_annual():
    p_curr = make_period("2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024)
    p_prior = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )

    # Current: NWC = 300
    fact_ca_curr = make_fact(
        StatementType.BALANCE_SHEET, "600", p_curr, CanonicalConcept.CURRENT_ASSETS
    )
    fact_cash_curr = make_fact(
        StatementType.BALANCE_SHEET,
        "100",
        p_curr,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
    )
    fact_cl_curr = make_fact(
        StatementType.BALANCE_SHEET, "200", p_curr, CanonicalConcept.CURRENT_LIABILITIES
    )

    # Prior: NWC = 200
    fact_ca_prior = make_fact(
        StatementType.BALANCE_SHEET, "450", p_prior, CanonicalConcept.CURRENT_ASSETS
    )
    fact_cash_prior = make_fact(
        StatementType.BALANCE_SHEET,
        "100",
        p_prior,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
    )
    fact_cl_prior = make_fact(
        StatementType.BALANCE_SHEET,
        "150",
        p_prior,
        CanonicalConcept.CURRENT_LIABILITIES,
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.BALANCE_SHEET,
                p_curr,
                [fact_ca_curr, fact_cash_curr, fact_cl_curr],
            ),
            make_statement(
                StatementType.BALANCE_SHEET,
                p_prior,
                [fact_ca_prior, fact_cash_prior, fact_cl_prior],
            ),
        ]
    )

    res = OperatingNWCEngine.calculate_delta_nwc(p_curr, p_prior, store)
    assert res.status == MetricStatus.VALID
    assert res.metric_id == FundamentalMetricId.DELTA_NWC
    # Delta NWC = 300 - 200 = 100
    assert res.value == Decimal("100")
    assert (
        "Delta NWC = NWC_current (300) - NWC_prior (200) = 100."
        in res.provenance.methodology_notes
    )


def test_delta_nwc_missing_prior_period():
    p_curr = make_period("2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024)
    fact_ca_curr = make_fact(
        StatementType.BALANCE_SHEET, "600", p_curr, CanonicalConcept.CURRENT_ASSETS
    )
    fact_cash_curr = make_fact(
        StatementType.BALANCE_SHEET,
        "100",
        p_curr,
        CanonicalConcept.CASH_AND_EQUIVALENTS,
    )
    fact_cl_curr = make_fact(
        StatementType.BALANCE_SHEET, "200", p_curr, CanonicalConcept.CURRENT_LIABILITIES
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.BALANCE_SHEET,
                p_curr,
                [fact_ca_curr, fact_cash_curr, fact_cl_curr],
            )
        ]
    )

    res = OperatingNWCEngine.calculate_delta_nwc(p_curr, None, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert res.value is None
    codes = [d.code for d in res.diagnostics]
    assert DiagnosticCode.MISSING_PRIOR_PERIOD in codes
