"""
tests.unit.domain.fundamental.test_growth_engine
================================================
Deterministic tests for GrowthEngine: Revenue YoY and QoQ calculations,
prior period matching, zero/negative base denominators, and provenance.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodLabel,
    FiscalPeriodType,
    StatementType,
)
from aurelius.domain.fundamental.engines.growth import GrowthEngine
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore
from tests.unit.domain.fundamental.conftest import (
    make_fact,
    make_period,
    make_statement,
)


def test_revenue_yoy_normal():
    p2023 = make_period("2023-12-31", fiscal_year=2023)
    p2024 = make_period("2024-12-31", fiscal_year=2024)

    fact2023 = make_fact(
        StatementType.INCOME_STATEMENT,
        "1000",
        p2023,
        CanonicalConcept.REVENUE,
        "Total Revenue",
    )
    fact2024 = make_fact(
        StatementType.INCOME_STATEMENT,
        "1250",
        p2024,
        CanonicalConcept.REVENUE,
        "Total Revenue",
    )

    stmt2023 = make_statement(StatementType.INCOME_STATEMENT, p2023, [fact2023])
    stmt2024 = make_statement(StatementType.INCOME_STATEMENT, p2024, [fact2024])
    store = MultiPeriodFactStore([stmt2023, stmt2024])

    res = GrowthEngine.calculate_revenue_growth_yoy(p2024, p2023, store)

    assert res.metric_id == FundamentalMetricId.REVENUE_GROWTH_YOY
    assert res.category == MetricCategory.GROWTH
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("0.25")
    assert res.formatted_value == "25.00%"
    assert fact2023.fact_id in res.provenance.source_fact_ids
    assert fact2024.fact_id in res.provenance.source_fact_ids
    assert res.provenance.formula_id == "FORMULA_REVENUE_GROWTH_YOY"


def test_revenue_yoy_missing_current_revenue():
    p2023 = make_period("2023-12-31", fiscal_year=2023)
    p2024 = make_period("2024-12-31", fiscal_year=2024)

    fact2023 = make_fact(
        StatementType.INCOME_STATEMENT, "1000", p2023, CanonicalConcept.REVENUE
    )
    stmt2023 = make_statement(StatementType.INCOME_STATEMENT, p2023, [fact2023])
    store = MultiPeriodFactStore([stmt2023])

    res = GrowthEngine.calculate_revenue_growth_yoy(p2024, p2023, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert res.value is None
    assert any(d.code == DiagnosticCode.MISSING_REQUIRED_FACT for d in res.diagnostics)


def test_revenue_yoy_missing_prior_period():
    p2024 = make_period("2024-12-31", fiscal_year=2024)
    fact2024 = make_fact(
        StatementType.INCOME_STATEMENT, "1250", p2024, CanonicalConcept.REVENUE
    )
    stmt2024 = make_statement(StatementType.INCOME_STATEMENT, p2024, [fact2024])
    store = MultiPeriodFactStore([stmt2024])

    res = GrowthEngine.calculate_revenue_growth_yoy(p2024, None, store)
    assert res.status == MetricStatus.UNAVAILABLE
    assert res.value is None
    assert any(d.code == DiagnosticCode.MISSING_PRIOR_PERIOD for d in res.diagnostics)


def test_revenue_yoy_zero_base():
    p2023 = make_period("2023-12-31", fiscal_year=2023)
    p2024 = make_period("2024-12-31", fiscal_year=2024)

    fact2023 = make_fact(
        StatementType.INCOME_STATEMENT, "0", p2023, CanonicalConcept.REVENUE
    )
    fact2024 = make_fact(
        StatementType.INCOME_STATEMENT, "500", p2024, CanonicalConcept.REVENUE
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p2023, [fact2023]),
            make_statement(StatementType.INCOME_STATEMENT, p2024, [fact2024]),
        ]
    )

    res = GrowthEngine.calculate_revenue_growth_yoy(p2024, p2023, store)
    assert res.status == MetricStatus.DISTORTED
    assert res.value is None
    assert any(d.code == DiagnosticCode.ZERO_DIVISION for d in res.diagnostics)


def test_revenue_yoy_negative_base():
    p2023 = make_period("2023-12-31", fiscal_year=2023)
    p2024 = make_period("2024-12-31", fiscal_year=2024)

    fact2023 = make_fact(
        StatementType.INCOME_STATEMENT, "-100", p2023, CanonicalConcept.REVENUE
    )
    fact2024 = make_fact(
        StatementType.INCOME_STATEMENT, "500", p2024, CanonicalConcept.REVENUE
    )

    store = MultiPeriodFactStore(
        [
            make_statement(StatementType.INCOME_STATEMENT, p2023, [fact2023]),
            make_statement(StatementType.INCOME_STATEMENT, p2024, [fact2024]),
        ]
    )

    res = GrowthEngine.calculate_revenue_growth_yoy(p2024, p2023, store)
    assert res.status == MetricStatus.DISTORTED
    assert res.value is None
    assert any(d.code == DiagnosticCode.NEGATIVE_BASE_REVENUE for d in res.diagnostics)


def test_revenue_qoq_normal():
    pq1 = make_period(
        "2024-03-31", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q1
    )
    pq2 = make_period(
        "2024-06-30", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q2
    )

    fact_q1 = make_fact(
        StatementType.INCOME_STATEMENT, "200", pq1, CanonicalConcept.REVENUE
    )
    fact_q2 = make_fact(
        StatementType.INCOME_STATEMENT, "220", pq2, CanonicalConcept.REVENUE
    )

    store = MultiPeriodFactStore(
        [
            make_statement(
                StatementType.INCOME_STATEMENT,
                pq1,
                [fact_q1],
                frequency=FiscalPeriodType.QUARTERLY,
            ),
            make_statement(
                StatementType.INCOME_STATEMENT,
                pq2,
                [fact_q2],
                frequency=FiscalPeriodType.QUARTERLY,
            ),
        ]
    )

    res = GrowthEngine.calculate_revenue_growth_qoq(
        pq2, pq1, FiscalPeriodType.QUARTERLY, store
    )
    assert res.status == MetricStatus.VALID
    assert res.value == Decimal("0.10")
    assert res.formatted_value == "10.00%"


def test_revenue_qoq_not_applicable_for_annual():
    p2024 = make_period("2024-12-31")
    store = MultiPeriodFactStore([])
    res = GrowthEngine.calculate_revenue_growth_qoq(
        p2024, None, FiscalPeriodType.ANNUAL, store
    )
    assert res.status == MetricStatus.NOT_APPLICABLE
    assert any(
        d.code == DiagnosticCode.PERIOD_ALIGNMENT_MISMATCH for d in res.diagnostics
    )
