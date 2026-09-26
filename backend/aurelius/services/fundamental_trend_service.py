"""
aurelius.services.fundamental_trend_service
============================================
Application service orchestrating multi-period fundamental trends,
period-over-period variations, and M4 calendar-time CAGR.

Key Invariants:
  - Canonical metrics:
      1. revenue
      2. revenue_growth
      3. gross_margin
      4. operating_margin
      5. net_margin
      6. roa
      7. roe
      8. roic
      9. cfo
      10. fcf
      11. fcf_margin
      12. cfo_to_net_income
      13. fcf_to_net_income
      14. debt_to_ebitda
      15. net_debt_to_ebitda
      16. cash_conversion_cycle
      17. cagr (with horizons: 3Y, 5Y)
  - Frequency rules:
      * ANNUAL: YoY only; QoQ is N/A.
      * QUARTERLY: QoQ and YoY.
      * TTM: Strictly "TTM Sequential Change", never "QoQ".
  - Calendar-Time CAGR (M4):
      * Requires calendar_days >= 365.
      * P_start <= 0 -> UNAVAILABLE.
      * No synthetic periods, no interpolation, no forward-fill.
"""

import logging

from fastapi import Depends

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodType,
    StatementType,
    Unit,
)
from aurelius.domain.errors import DataNotFoundError
from aurelius.domain.fundamental.engines.trend_engine import (
    CAGRResult,
    TrendEngine,
    TrendPoint,
)
from aurelius.domain.fundamental.enums import (
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.models import MetricProvenance, MetricResult
from aurelius.domain.validation import validate_ticker
from aurelius.services.fundamental_service import (
    FundamentalAnalysisService,
    get_fundamental_analysis_service,
)

logger = logging.getLogger(__name__)


class FundamentalTrendService:
    """
    Application service orchestrating historical fundamental trajectories and compound growth.
    """

    def __init__(self, fundamental_service: FundamentalAnalysisService) -> None:
        self.fundamental_service = fundamental_service

    async def get_fundamental_trends(
        self,
        ticker: str,
        frequency: FiscalPeriodType = FiscalPeriodType.ANNUAL,
        metrics: list[str] | None = None,
        limit: int = 10,
    ) -> tuple[
        str, FiscalPeriodType, dict[str, list[TrendPoint]], dict[str, list[CAGRResult]]
    ]:
        """
        Orchestrate historical trend trajectories and CAGR calculations.

        Returns:
          (ticker, frequency, series_by_metric, cagr_by_metric)
        """
        normalized_ticker = validate_ticker(ticker)
        effective_limit = max(1, min(limit, 20))

        # 1. Fetch comprehensive fundamental report across all periods
        report = await self.fundamental_service.get_fundamental_report(
            ticker=normalized_ticker,
            frequency=frequency,
            allow_point_in_time_fallback=False,
        )

        if not report.periods:
            raise DataNotFoundError(
                ticker=normalized_ticker,
                message=f"No financial periods available to construct fundamental trends for {normalized_ticker}.",
            )

        # Slice to the most recent `effective_limit` periods
        sliced_periods = report.periods[-effective_limit:]
        sliced_keys = {p.period_key for p in sliced_periods}

        # Determine metric list
        requested_metrics = metrics if metrics else TrendEngine.CANONICAL_TREND_METRICS

        # Map canonical trend metrics to FundamentalReport keys
        metric_key_mapping: dict[str, str] = {
            "revenue": FundamentalMetricId.REVENUE.value,
            "revenue_growth": FundamentalMetricId.REVENUE_GROWTH_YOY.value,
            "gross_margin": FundamentalMetricId.GROSS_PROFIT_MARGIN.value,
            "operating_margin": FundamentalMetricId.OPERATING_MARGIN.value,
            "net_margin": FundamentalMetricId.NET_PROFIT_MARGIN.value,
            "roa": FundamentalMetricId.RETURN_ON_ASSETS.value,
            "roe": FundamentalMetricId.RETURN_ON_EQUITY.value,
            "cfo": FundamentalMetricId.OPERATING_CASH_FLOW.value,
            "fcf": FundamentalMetricId.FREE_CASH_FLOW.value,
            "fcf_margin": FundamentalMetricId.FCF_MARGIN.value,
            "cfo_to_net_income": FundamentalMetricId.CFO_TO_NET_INCOME.value,
            "fcf_to_net_income": FundamentalMetricId.FCF_CONVERSION.value,
            "debt_to_ebitda": FundamentalMetricId.DEBT_TO_EBITDA.value,
            "net_debt_to_ebitda": FundamentalMetricId.NET_DEBT_TO_EBITDA.value,
            "cash_conversion_cycle": FundamentalMetricId.CASH_CONVERSION_CYCLE.value,
        }

        series_dict: dict[str, list[TrendPoint]] = {}
        cagr_dict: dict[str, list[CAGRResult]] = {}

        # Build trajectory for each requested metric
        for m_name in requested_metrics:
            if m_name == "cagr":
                continue

            results_for_metric: list[MetricResult] = []

            # Handle ROIC separately as it is computed via ROICEngine
            if m_name == "roic":
                # For each period in sliced_periods, calculate ROIC
                for p in sliced_periods:
                    try:
                        # Use get_advanced_fundamentals to extract ROIC
                        adv = await self.fundamental_service.get_advanced_fundamentals(
                            ticker=normalized_ticker,
                            frequency=frequency,
                            fiscal_year=p.fiscal_year,
                            fiscal_period=p.fiscal_period.value
                            if p.fiscal_period
                            else None,
                        )
                        results_for_metric.append(adv[6])  # roic is 6th element
                    except Exception:
                        results_for_metric.append(
                            MetricResult(
                                metric_id=FundamentalMetricId.ROIC,
                                category=MetricCategory.PROFITABILITY,
                                status=MetricStatus.UNAVAILABLE,
                                value=None,
                                unit=Unit.PERCENT,
                                currency=None,
                                period=p,
                                provenance=MetricProvenance(formula_id="FORMULA_ROIC"),
                            )
                        )
            elif m_name == "revenue" and frequency != FiscalPeriodType.TTM:
                # Fetch income statements to extract revenue facts directly
                try:
                    inc_stmts = (
                        await self.fundamental_service.statement_service.get_statements(
                            normalized_ticker,
                            StatementType.INCOME_STATEMENT,
                            frequency,
                        )
                    )
                    stmt_by_key = {s.period.period_key: s for s in inc_stmts}
                    for p in sliced_periods:
                        s = stmt_by_key.get(p.period_key)
                        rev_fact = None
                        if s:
                            for f in s.facts:
                                if (
                                    f.concept.canonical_concept
                                    == CanonicalConcept.REVENUE
                                ):
                                    rev_fact = f
                                    break
                        if rev_fact is not None:
                            results_for_metric.append(
                                MetricResult(
                                    metric_id=FundamentalMetricId.REVENUE,
                                    category=MetricCategory.GROWTH,
                                    status=MetricStatus.VALID,
                                    value=rev_fact.value,
                                    unit=rev_fact.unit,
                                    currency=rev_fact.currency,
                                    period=p,
                                    provenance=MetricProvenance(
                                        formula_id="FORMULA_REVENUE",
                                        source_fact_ids=[rev_fact.fact_id],
                                        source_concepts=["REVENUE"],
                                        source_periods=[p.period_key],
                                    ),
                                )
                            )
                        else:
                            results_for_metric.append(
                                MetricResult(
                                    metric_id=FundamentalMetricId.REVENUE,
                                    category=MetricCategory.GROWTH,
                                    status=MetricStatus.UNAVAILABLE,
                                    value=None,
                                    unit=Unit.CURRENCY,
                                    currency=None,
                                    period=p,
                                    provenance=MetricProvenance(
                                        formula_id="FORMULA_REVENUE",
                                        source_concepts=["REVENUE"],
                                        source_periods=[p.period_key],
                                    ),
                                )
                            )
                except Exception as exc:
                    logger.warning("Failed to extract revenue facts for trend: %s", exc)
            else:
                rep_key = metric_key_mapping.get(m_name)
                if rep_key and rep_key in report.metrics:
                    raw_results = report.metrics[rep_key]
                    results_for_metric = [
                        r for r in raw_results if r.period.period_key in sliced_keys
                    ]

            if results_for_metric:
                trajectory = TrendEngine.compute_trend_trajectory(
                    results_for_metric, frequency
                )
                series_dict[m_name] = trajectory

                # Calculate CAGR for eligible level metrics over 3Y and 5Y horizons
                if m_name in ("revenue", "cfo", "fcf") and len(trajectory) >= 2:
                    cagr_list: list[CAGRResult] = []
                    valid_points = [
                        p
                        for p in trajectory
                        if p.status == MetricStatus.VALID and p.value is not None
                    ]

                    if len(valid_points) >= 2:
                        end_pt = valid_points[-1]

                        # 3Y Horizon lookup
                        start_3y_cand = None
                        if end_pt.period.fiscal_year:
                            target_3y_fy = end_pt.period.fiscal_year - 3
                            for pt in valid_points:
                                if pt.period.fiscal_year == target_3y_fy and (
                                    pt.period.fiscal_period
                                    == end_pt.period.fiscal_period
                                    or frequency == FiscalPeriodType.ANNUAL
                                ):
                                    start_3y_cand = pt
                                    break
                        if start_3y_cand:
                            res_3y = TrendEngine.calculate_calendar_cagr(
                                start_value=start_3y_cand.value,
                                end_value=end_pt.value,
                                start_period=start_3y_cand.period,
                                end_period=end_pt.period,
                                metric_name=m_name,
                                horizon="3Y",
                            )
                            cagr_list.append(res_3y)

                        # 5Y Horizon lookup
                        start_5y_cand = None
                        if end_pt.period.fiscal_year:
                            target_5y_fy = end_pt.period.fiscal_year - 5
                            for pt in valid_points:
                                if pt.period.fiscal_year == target_5y_fy and (
                                    pt.period.fiscal_period
                                    == end_pt.period.fiscal_period
                                    or frequency == FiscalPeriodType.ANNUAL
                                ):
                                    start_5y_cand = pt
                                    break
                        if start_5y_cand:
                            res_5y = TrendEngine.calculate_calendar_cagr(
                                start_value=start_5y_cand.value,
                                end_value=end_pt.value,
                                start_period=start_5y_cand.period,
                                end_period=end_pt.period,
                                metric_name=m_name,
                                horizon="5Y",
                            )
                            cagr_list.append(res_5y)

                    if cagr_list:
                        cagr_dict[m_name] = cagr_list

        return normalized_ticker, frequency, series_dict, cagr_dict


def get_fundamental_trend_service(
    fundamental_service: FundamentalAnalysisService = Depends(
        get_fundamental_analysis_service
    ),
) -> FundamentalTrendService:
    """
    FastAPI dependency provider for FundamentalTrendService.
    Accepts FundamentalAnalysisService via Depends so that dependency_overrides
    propagate correctly in tests.
    """
    return FundamentalTrendService(fundamental_service=fundamental_service)
