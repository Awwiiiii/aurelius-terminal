"""
tests.unit.domain.fundamental.test_profitability_engine
======================================================
Deterministic tests for ProfitabilityEngine: Gross profit resolution (reported vs derived),
negative EBIT operating margin, ROA two-point averaging and fallback, ROE negative equity,
and reported EBITDA margin restriction.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    PeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.profitability import ProfitabilityEngine
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


def test_reported_gross_profit_preferred():
    p = make_period("2024-12-31")
    fact_gp = make_fact(
        StatementType.INCOME_STATEMENT, "600", p, CanonicalConcept.GROSS_PROFIT
    )
    fact_rev = make_fact(
        StatementType.INCOME_STATEMENT, "1000", p, CanonicalConcept.REVENUE
    )
    fact_cogs = make_fact(
        StatementType.INCOME_STATEMENT, "350", p, CanonicalConcept.COST_OF_REVENUE
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.INCOME_STATEMENT, p, [fact_gp, fact_rev, fact_cogs]
            )
        ]
    )

    margin_res = ProfitabilityEngine.calculate_gross_margin(p, store)
    assert margin_res.status == MetricStatus.VALID
    assert margin_res.value == Decimal("0.6")
    assert margin_res.formatted_value == "60.00%"
    assert margin_res.provenance.formula_id == "FORMULA_GROSS_MARGIN_FROM_REPORTED_GP"
    assert fact_gp.fact_id in margin_res.provenance.source_fact_ids


def test_derived_gross_profit_when_reported_missing():
    p = make_period("2024-12-31")
    fact_rev = make_fact(
        StatementType.INCOME_STATEMENT,
        "1000",
        p,
        CanonicalConcept.REVENUE,
        fact_id="f_rev",
    )
    fact_cogs = make_fact(
        StatementType.INCOME_STATEMENT,
        "400",
        p,
        CanonicalConcept.COST_OF_REVENUE,
        fact_id="f_cogs",
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.INCOME_STATEMENT, p, [fact_rev, fact_cogs])]
    )

    gp_res = ProfitabilityEngine.calculate_gross_profit(p, store)
    assert gp_res.status == MetricStatus.VALID
    assert gp_res.value == Decimal("600")
    assert gp_res.is_derived is True
    assert "f_rev" in gp_res.provenance.source_fact_ids
    assert "f_cogs" in gp_res.provenance.source_fact_ids
    assert gp_res.provenance.formula_id == "FORMULA_GROSS_PROFIT_FROM_REVENUE_COGS"
    assert "Revenue minus Cost of Revenue" in (
        gp_res.provenance.methodology_notes or ""
    )

    margin_res = ProfitabilityEngine.calculate_gross_margin(p, store)
    assert margin_res.status == MetricStatus.VALID
    assert margin_res.value == Decimal("0.6")
    assert margin_res.provenance.formula_id == "FORMULA_GROSS_MARGIN_FROM_DERIVED_GP"


def test_missing_gross_profit_inputs():
    p = make_period("2024-12-31")
    store = MultiPeriodFactStore([])

    res = ProfitabilityEngine.calculate_gross_margin(p, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(d.code == DiagnosticCode.MISSING_REQUIRED_FACT for d in res.diagnostics)


def test_gross_margin_zero_revenue():
    p = make_period("2024-12-31")
    fact_rev = make_fact(
        StatementType.INCOME_STATEMENT, "0", p, CanonicalConcept.REVENUE
    )
    store = MultiPeriodFactStore(
        [make_statement(StatementType.INCOME_STATEMENT, p, [fact_rev])]
    )

    res = ProfitabilityEngine.calculate_gross_margin(p, store)
    assert res.status == MetricStatus.DISTORTED
    assert any(
        d.code == DiagnosticCode.ZERO_OR_NEGATIVE_REVENUE for d in res.diagnostics
    )


def test_operating_margin_negative_ebit_valid():
    p = make_period("2024-12-31")
    fact_rev = make_fact(
        StatementType.INCOME_STATEMENT, "1000", p, CanonicalConcept.REVENUE
    )
    fact_ebit = make_fact(
        StatementType.INCOME_STATEMENT, "-150", p, CanonicalConcept.OPERATING_INCOME
    )

    store = MultiPeriodFactStore(
        [make_statement(StatementType.INCOME_STATEMENT, p, [fact_rev, fact_ebit])]
    )

    res = ProfitabilityEngine.calculate_operating_margin(p, store)
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("-0.15")
    assert res.formatted_value == "-15.00%"


def test_roa_two_point_average_normal():
    p_prior = make_period("2023-12-31", fiscal_year=2023)
    p_curr = make_period("2024-12-31", fiscal_year=2024)

    p_prior_inst = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )
    p_curr_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )

    fact_ni = make_fact(
        StatementType.INCOME_STATEMENT, "120", p_curr, CanonicalConcept.NET_INCOME
    )
    fact_assets_prior = make_fact(
        StatementType.BALANCE_SHEET, "1000", p_prior_inst, CanonicalConcept.TOTAL_ASSETS
    )
    fact_assets_curr = make_fact(
        StatementType.BALANCE_SHEET, "1400", p_curr_inst, CanonicalConcept.TOTAL_ASSETS
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p_curr, [fact_ni]),
            make_statement(
                StatementType.BALANCE_SHEET, p_prior_inst, [fact_assets_prior]
            ),
            make_statement(
                StatementType.BALANCE_SHEET, p_curr_inst, [fact_assets_curr]
            ),
        ]
    )

    res = ProfitabilityEngine.calculate_roa(p_curr, p_prior, store)
    assert res.status == MetricStatus.VALID
    # Average assets = (1000 + 1400) / 2 = 1200; ROA = 120 / 1200 = 0.10 (10%)
    assert res.value == Decimal("0.1")
    assert res.formatted_value == "10.00%"
    assert res.provenance.formula_id == "FORMULA_ROA_2PT_AVG"


def test_roa_missing_prior_unavailable_by_default():
    p_curr = make_period("2024-12-31")
    p_curr_inst = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    fact_ni = make_fact(
        StatementType.INCOME_STATEMENT, "120", p_curr, CanonicalConcept.NET_INCOME
    )
    fact_assets = make_fact(
        StatementType.BALANCE_SHEET, "1200", p_curr_inst, CanonicalConcept.TOTAL_ASSETS
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p_curr, [fact_ni]),
            make_statement(StatementType.BALANCE_SHEET, p_curr_inst, [fact_assets]),
        ]
    )

    # Default: allow_point_in_time_fallback=False
    res = ProfitabilityEngine.calculate_roa(
        p_curr, None, store, allow_point_in_time_fallback=False
    )
    assert res.status == MetricStatus.UNAVAILABLE
    assert res.value is None
    assert any(
        d.code == DiagnosticCode.INSUFFICIENT_PERIODS_FOR_AVERAGE
        for d in res.diagnostics
    )


def test_roa_fallback_point_in_time():
    p_curr = make_period("2024-12-31")
    p_curr_inst = make_period("2024-12-31", period_type=PeriodType.INSTANT)

    fact_ni = make_fact(
        StatementType.INCOME_STATEMENT, "120", p_curr, CanonicalConcept.NET_INCOME
    )
    fact_assets = make_fact(
        StatementType.BALANCE_SHEET, "1200", p_curr_inst, CanonicalConcept.TOTAL_ASSETS
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p_curr, [fact_ni]),
            make_statement(StatementType.BALANCE_SHEET, p_curr_inst, [fact_assets]),
        ]
    )

    res = ProfitabilityEngine.calculate_roa(
        p_curr, None, store, allow_point_in_time_fallback=True
    )
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("0.1")
    assert any(
        d.code == DiagnosticCode.POINT_IN_TIME_DENOMINATOR_FALLBACK
        for d in res.diagnostics
    )
    assert res.provenance.formula_id == "FORMULA_ROA_POINT_IN_TIME"


def test_roe_negative_equity_distorted():
    p_prior = make_period("2023-12-31", fiscal_year=2023)
    p_curr = make_period("2024-12-31", fiscal_year=2024)

    p_prior_inst = make_period(
        "2023-12-31", period_type=PeriodType.INSTANT, fiscal_year=2023
    )
    p_curr_inst = make_period(
        "2024-12-31", period_type=PeriodType.INSTANT, fiscal_year=2024
    )

    fact_ni = make_fact(
        StatementType.INCOME_STATEMENT, "50", p_curr, CanonicalConcept.NET_INCOME
    )
    fact_eq_prior = make_fact(
        StatementType.BALANCE_SHEET,
        "-200",
        p_prior_inst,
        CanonicalConcept.STOCKHOLDERS_EQUITY,
    )
    fact_eq_curr = make_fact(
        StatementType.BALANCE_SHEET,
        "-100",
        p_curr_inst,
        CanonicalConcept.STOCKHOLDERS_EQUITY,
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p_curr, [fact_ni]),
            make_statement(StatementType.BALANCE_SHEET, p_prior_inst, [fact_eq_prior]),
            make_statement(StatementType.BALANCE_SHEET, p_curr_inst, [fact_eq_curr]),
        ]
    )

    res = ProfitabilityEngine.calculate_roe(p_curr, p_prior, store)
    assert res.status == MetricStatus.DISTORTED
    assert res.value is None
    assert any(
        d.code == DiagnosticCode.NEGATIVE_OR_ZERO_EQUITY for d in res.diagnostics
    )


def test_ebitda_margin_requires_reported_ebitda():
    p = make_period("2024-12-31")
    fact_rev = make_fact(
        StatementType.INCOME_STATEMENT, "1000", p, CanonicalConcept.REVENUE
    )
    store = MultiPeriodFactStore(
        [make_statement(StatementType.INCOME_STATEMENT, p, [fact_rev])]
    )

    res = ProfitabilityEngine.calculate_ebitda_margin(p, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.NON_REPORTED_EBITDA_RESTRICTION
        for d in res.diagnostics
    )

    # When reported EBITDA exists
    fact_ebitda = make_fact(
        StatementType.INCOME_STATEMENT, "300", p, CanonicalConcept.EBITDA
    )
    store2 = MultiPeriodFactStore(
        [make_statement(StatementType.INCOME_STATEMENT, p, [fact_rev, fact_ebitda])]
    )
    res2 = ProfitabilityEngine.calculate_ebitda_margin(p, store2)
    assert res2.status == MetricStatus.VALID
    assert res2.value == Decimal("0.3")
    assert res2.formatted_value == "30.00%"
