"""
tests.unit.domain.fundamental.test_trend_engine
================================================
Unit tests for Fundamental Trends, Period-over-Period Variations,
and M4 Calendar-Time CAGR.
"""

from decimal import Decimal

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    FiscalPeriodLabel,
    FiscalPeriodType,
    Unit,
)
from aurelius.domain.fundamental.engines.trend_engine import TrendEngine
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.models import (
    MetricProvenance,
    MetricResult,
)
from tests.unit.domain.fundamental.conftest import make_period


def test_calendar_cagr_m4_formula_normal_3y_and_5y():
    # 3 years: 2021-12-31 to 2024-12-31 (1096 days)
    # Start = 100.0, End = 133.1 (approx 10% annual growth)
    p_start = make_period("2021-12-31", fiscal_year=2021)
    p_end = make_period("2024-12-31", fiscal_year=2024)

    res_3y = TrendEngine.calculate_calendar_cagr(
        start_value=Decimal("100.0"),
        end_value=Decimal("133.1"),
        start_period=p_start,
        end_period=p_end,
        metric_name="revenue",
        horizon="3Y",
    )
    assert res_3y.status == MetricStatus.VALID
    assert res_3y.calendar_days == 1096
    # Approx 0.1000
    assert abs(res_3y.cagr - Decimal("0.1000")) <= Decimal("0.0010")


def test_calendar_cagr_insufficient_days():
    # Only 180 days
    p_start = make_period("2024-01-01", fiscal_year=2024)
    p_end = make_period("2024-06-29", fiscal_year=2024)

    res = TrendEngine.calculate_calendar_cagr(
        start_value=Decimal("100.0"),
        end_value=Decimal("120.0"),
        start_period=p_start,
        end_period=p_end,
        metric_name="revenue",
        horizon="1Y",
    )
    assert res.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.INSUFFICIENT_CALENDAR_DAYS for d in res.diagnostics
    )


def test_calendar_cagr_non_positive_starting_value():
    p_start = make_period("2021-12-31", fiscal_year=2021)
    p_end = make_period("2024-12-31", fiscal_year=2024)

    res_zero = TrendEngine.calculate_calendar_cagr(
        start_value=Decimal("0.0"),
        end_value=Decimal("150.0"),
        start_period=p_start,
        end_period=p_end,
        metric_name="fcf",
        horizon="3Y",
    )
    assert res_zero.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.NON_POSITIVE_STARTING_VALUE
        for d in res_zero.diagnostics
    )

    res_neg = TrendEngine.calculate_calendar_cagr(
        start_value=Decimal("-25.0"),
        end_value=Decimal("150.0"),
        start_period=p_start,
        end_period=p_end,
        metric_name="fcf",
        horizon="3Y",
    )
    assert res_neg.status == MetricStatus.UNAVAILABLE
    assert any(
        d.code == DiagnosticCode.NON_POSITIVE_STARTING_VALUE
        for d in res_neg.diagnostics
    )


def test_compute_trend_trajectory_annual():
    p22 = make_period("2022-12-31", fiscal_year=2022)
    p23 = make_period("2023-12-31", fiscal_year=2023)
    p24 = make_period("2024-12-31", fiscal_year=2024)

    m22 = MetricResult(
        metric_id=FundamentalMetricId.REVENUE,
        category=MetricCategory.GROWTH,
        status=MetricStatus.VALID,
        value=Decimal("100.0"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        period=p22,
        provenance=MetricProvenance(formula_id="FORMULA_REVENUE"),
    )
    m23 = MetricResult(
        metric_id=FundamentalMetricId.REVENUE,
        category=MetricCategory.GROWTH,
        status=MetricStatus.VALID,
        value=Decimal("120.0"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        period=p23,
        provenance=MetricProvenance(formula_id="FORMULA_REVENUE"),
    )
    m24 = MetricResult(
        metric_id=FundamentalMetricId.REVENUE,
        category=MetricCategory.GROWTH,
        status=MetricStatus.VALID,
        value=Decimal("150.0"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        period=p24,
        provenance=MetricProvenance(formula_id="FORMULA_REVENUE"),
    )

    trajectory = TrendEngine.compute_trend_trajectory(
        [m22, m23, m24], FiscalPeriodType.ANNUAL
    )
    assert len(trajectory) == 3

    # Point 0: 2022
    assert trajectory[0].qoq_change is None
    assert trajectory[0].yoy_change is None

    # Point 1: 2023 -> YoY = (120 - 100) / 100 = 0.20 (20%)
    assert trajectory[1].qoq_change is None
    assert trajectory[1].yoy_change == Decimal("0.20")

    # Point 2: 2024 -> YoY = (150 - 120) / 120 = 0.25 (25%)
    assert trajectory[2].qoq_change is None
    assert trajectory[2].yoy_change == Decimal("0.25")


def test_compute_trend_trajectory_quarterly():
    q1_23 = make_period(
        "2023-03-31", fiscal_year=2023, fiscal_period=FiscalPeriodLabel.Q1
    )
    q2_23 = make_period(
        "2023-06-30", fiscal_year=2023, fiscal_period=FiscalPeriodLabel.Q2
    )
    q1_24 = make_period(
        "2024-03-31", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.Q1
    )

    m1_23 = MetricResult(
        metric_id=FundamentalMetricId.REVENUE,
        category=MetricCategory.GROWTH,
        status=MetricStatus.VALID,
        value=Decimal("100.0"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        period=q1_23,
        provenance=MetricProvenance(formula_id="FORMULA_REVENUE"),
    )
    m2_23 = MetricResult(
        metric_id=FundamentalMetricId.REVENUE,
        category=MetricCategory.GROWTH,
        status=MetricStatus.VALID,
        value=Decimal("110.0"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        period=q2_23,
        provenance=MetricProvenance(formula_id="FORMULA_REVENUE"),
    )
    m1_24 = MetricResult(
        metric_id=FundamentalMetricId.REVENUE,
        category=MetricCategory.GROWTH,
        status=MetricStatus.VALID,
        value=Decimal("125.0"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        period=q1_24,
        provenance=MetricProvenance(formula_id="FORMULA_REVENUE"),
    )

    trajectory = TrendEngine.compute_trend_trajectory(
        [m1_23, m2_23, m1_24], FiscalPeriodType.QUARTERLY
    )

    # Q2 2023: QoQ = (110 - 100) / 100 = 0.10
    assert trajectory[1].qoq_change == Decimal("0.10")

    # Q1 2024: YoY vs Q1 2023 = (125 - 100) / 100 = 0.25
    assert trajectory[2].yoy_change == Decimal("0.25")


def test_compute_trend_trajectory_ttm_sequential():
    t1 = make_period(
        "2024-06-30", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.TTM
    )
    t2 = make_period(
        "2024-09-30", fiscal_year=2024, fiscal_period=FiscalPeriodLabel.TTM
    )

    mt1 = MetricResult(
        metric_id=FundamentalMetricId.REVENUE,
        category=MetricCategory.GROWTH,
        status=MetricStatus.VALID,
        value=Decimal("1000.0"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        period=t1,
        provenance=MetricProvenance(formula_id="FORMULA_TTM_REVENUE"),
    )
    mt2 = MetricResult(
        metric_id=FundamentalMetricId.REVENUE,
        category=MetricCategory.GROWTH,
        status=MetricStatus.VALID,
        value=Decimal("1050.0"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        period=t2,
        provenance=MetricProvenance(formula_id="FORMULA_TTM_REVENUE"),
    )

    trajectory = TrendEngine.compute_trend_trajectory([mt1, mt2], FiscalPeriodType.TTM)

    # Must be ttm_sequential_change, NEVER qoq_change!
    assert trajectory[1].qoq_change is None
    assert trajectory[1].ttm_sequential_change == Decimal("0.05")
