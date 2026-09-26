"""
aurelius.domain.fundamental.engines.trend_engine
================================================
Pure calculation engine for Fundamental Trends, Period-over-Period Variations,
and M4 Calendar-Time Compound Annual Growth Rates (CAGR).

Canonical Metrics Supported:
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

Frequency Semantics:
  - ANNUAL: YoY change supported; QoQ = N/A.
  - QUARTERLY:
      * QoQ change = current quarter / immediately prior chronological quarter - 1.
      * YoY change = current quarter / same fiscal quarter of prior fiscal year - 1.
  - TTM:
      * Labeled strictly as "TTM Sequential Change" or "TTM vs Previous TTM".
      * NEVER labeled as "QoQ".

CAGR Methodology (reusing M4 calendar-time formulation):
  CAGR = (P_end / P_start) ** (365.2425 / calendar_days) - 1.
  Requirements:
    - calendar_days >= 365
    - P_start > 0 and P_end > 0
    - If P_start <= 0 -> UNAVAILABLE with NON_POSITIVE_STARTING_VALUE.
    - If calendar_days < 365 -> UNAVAILABLE with INSUFFICIENT_CALENDAR_DAYS.
    - No interpolation, no forward fill, no fabricated intermediate periods.
"""

import math
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.financials import (
    FinancialPeriod,
    FiscalPeriodLabel,
    FiscalPeriodType,
)
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    MetricStatus,
)
from aurelius.domain.fundamental.models import (
    MetricDiagnostic,
    MetricProvenance,
    MetricResult,
)


class TrendPoint(BaseModel):
    """
    A single point in a fundamental trend trajectory.
    """

    model_config = ConfigDict(frozen=True)

    period: FinancialPeriod = Field(..., description="Financial period represented.")
    value: Decimal | None = Field(default=None, description="Calculated metric value.")
    status: MetricStatus = Field(
        default=MetricStatus.VALID, description="Operational status."
    )
    qoq_change: Decimal | None = Field(
        default=None, description="Sequential quarter-over-quarter percentage change."
    )
    yoy_change: Decimal | None = Field(
        default=None, description="Year-over-year percentage change."
    )
    ttm_sequential_change: Decimal | None = Field(
        default=None, description="TTM vs Previous TTM sequential percentage change."
    )
    diagnostics: list[MetricDiagnostic] = Field(default_factory=list)
    provenance: MetricProvenance = Field(
        ..., description="Audit provenance for this point."
    )


class CAGRResult(BaseModel):
    """
    Compound Annual Growth Rate calculation result over a multi-year horizon.
    """

    model_config = ConfigDict(frozen=True)

    metric_name: str = Field(..., description="Target canonical metric name.")
    horizon: str = Field(..., description="'3Y' or '5Y'.")
    cagr: Decimal | None = Field(
        default=None, description="Annualized compound rate (e.g. 0.125 for 12.5%)."
    )
    status: MetricStatus = Field(
        default=MetricStatus.VALID, description="Operational status."
    )
    start_period: FinancialPeriod = Field(..., description="Anchor start period.")
    end_period: FinancialPeriod = Field(..., description="Anchor end period.")
    start_value: Decimal | None = Field(
        default=None, description="Starting metric value."
    )
    end_value: Decimal | None = Field(default=None, description="Ending metric value.")
    calendar_days: int = Field(
        ..., description="Exact elapsed calendar days between cutoff dates."
    )
    diagnostics: list[MetricDiagnostic] = Field(default_factory=list)
    provenance: MetricProvenance = Field(..., description="Audit provenance.")


class TrendEngine:
    """
    Pure calculation engine for multi-period fundamental trajectories and CAGR.
    """

    METHODOLOGY_VERSION = "1.0.0"

    CANONICAL_TREND_METRICS = [
        "revenue",
        "revenue_growth",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "roa",
        "roe",
        "roic",
        "cfo",
        "fcf",
        "fcf_margin",
        "cfo_to_net_income",
        "fcf_to_net_income",
        "debt_to_ebitda",
        "net_debt_to_ebitda",
        "cash_conversion_cycle",
        "cagr",
    ]

    @classmethod
    def calculate_calendar_cagr(
        cls,
        start_value: Decimal | None,
        end_value: Decimal | None,
        start_period: FinancialPeriod,
        end_period: FinancialPeriod,
        metric_name: str,
        horizon: str,
    ) -> CAGRResult:
        """
        Calculate calendar-time CAGR strictly adhering to M4 specifications:
          CAGR = (P_end / P_start) ** (365.2425 / calendar_days) - 1.

        Requirements:
          - calendar_days >= 365
          - P_start > 0 and P_end > 0
          - No interpolation, no synthetic periods
        """
        start_date = start_period.end_date or start_period.instant_date
        end_date = end_period.end_date or end_period.instant_date

        if start_date is None or end_date is None:
            return CAGRResult(
                metric_name=metric_name,
                horizon=horizon,
                cagr=None,
                status=MetricStatus.UNAVAILABLE,
                start_period=start_period,
                end_period=end_period,
                start_value=start_value,
                end_value=end_value,
                calendar_days=0,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Missing start or end period cutoff date for calendar-time CAGR.",
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CALENDAR_CAGR",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_periods=[start_period.period_key, end_period.period_key],
                ),
            )

        calendar_days = (end_date - start_date).days

        # Check calendar_days >= 365
        if calendar_days < 365:
            return CAGRResult(
                metric_name=metric_name,
                horizon=horizon,
                cagr=None,
                status=MetricStatus.UNAVAILABLE,
                start_period=start_period,
                end_period=end_period,
                start_value=start_value,
                end_value=end_value,
                calendar_days=calendar_days,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.INSUFFICIENT_CALENDAR_DAYS,
                        message=f"Elapsed calendar days ({calendar_days}) is less than minimum required 365 days for CAGR.",
                        details={"calendar_days": str(calendar_days)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CALENDAR_CAGR",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_periods=[start_period.period_key, end_period.period_key],
                ),
            )

        # Check missing or non-positive starting value
        if start_value is None or end_value is None:
            return CAGRResult(
                metric_name=metric_name,
                horizon=horizon,
                cagr=None,
                status=MetricStatus.UNAVAILABLE,
                start_period=start_period,
                end_period=end_period,
                start_value=start_value,
                end_value=end_value,
                calendar_days=calendar_days,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Start value or end value is missing for CAGR calculation.",
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CALENDAR_CAGR",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_periods=[start_period.period_key, end_period.period_key],
                ),
            )

        if start_value <= Decimal("0"):
            return CAGRResult(
                metric_name=metric_name,
                horizon=horizon,
                cagr=None,
                status=MetricStatus.UNAVAILABLE,
                start_period=start_period,
                end_period=end_period,
                start_value=start_value,
                end_value=end_value,
                calendar_days=calendar_days,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_STARTING_VALUE,
                        message="Starting metric value is zero or negative; CAGR is mathematically uncomputable.",
                        details={"start_value": str(start_value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CALENDAR_CAGR",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_periods=[start_period.period_key, end_period.period_key],
                    methodology_notes="CAGR formula requires strictly positive starting value.",
                ),
            )

        if end_value <= Decimal("0"):
            return CAGRResult(
                metric_name=metric_name,
                horizon=horizon,
                cagr=None,
                status=MetricStatus.UNAVAILABLE,
                start_period=start_period,
                end_period=end_period,
                start_value=start_value,
                end_value=end_value,
                calendar_days=calendar_days,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Ending metric value is zero or negative; real-valued fractional power is undefined.",
                        details={"end_value": str(end_value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CALENDAR_CAGR",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_periods=[start_period.period_key, end_period.period_key],
                ),
            )

        # M4 calendar-time formulation: (P_end / P_start) ** (365.2425 / calendar_days) - 1
        ratio = float(end_value / start_value)
        exponent = 365.2425 / float(calendar_days)
        cagr_float = math.pow(ratio, exponent) - 1.0
        cagr_dec = Decimal(str(round(cagr_float, 8))).quantize(Decimal("0.0001"))

        return CAGRResult(
            metric_name=metric_name,
            horizon=horizon,
            cagr=cagr_dec,
            status=MetricStatus.VALID,
            start_period=start_period,
            end_period=end_period,
            start_value=start_value,
            end_value=end_value,
            calendar_days=calendar_days,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_CALENDAR_CAGR",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_periods=[start_period.period_key, end_period.period_key],
                methodology_notes=f"M4 Calendar-Time CAGR across {calendar_days} days: (P_end / P_start) ^ (365.2425 / {calendar_days}) - 1.",
            ),
        )

    @classmethod
    def compute_trend_trajectory(
        cls,
        metric_results: list[MetricResult],
        frequency: FiscalPeriodType,
    ) -> list[TrendPoint]:
        """
        Build an aligned chronological trajectory of TrendPoints with period variations.
        Rules:
          - ANNUAL: YoY change only. QoQ = N/A.
          - QUARTERLY: QoQ change (immediate prior quarter) and YoY change (same quarter prior year).
          - TTM: Labeled strictly as "ttm_sequential_change" (never QoQ).
        """

        # Sort chronologically by period cutoff
        def _sort_key(m: MetricResult) -> tuple[date, int, str]:
            cutoff = m.period.instant_date or m.period.end_date or date.min
            yr = m.period.fiscal_year or m.period.calendar_year or cutoff.year
            return (cutoff, yr, m.period.period_key)

        sorted_results = sorted(metric_results, key=_sort_key)
        points: list[TrendPoint] = []

        by_fy_fq = {
            (m.period.fiscal_year, m.period.fiscal_period): m
            for m in sorted_results
            if m.period.fiscal_year is not None and m.period.fiscal_period is not None
        }

        for i, m in enumerate(sorted_results):
            curr_val = m.value if m.status == MetricStatus.VALID else None
            curr_period = m.period

            qoq_change: Decimal | None = None
            yoy_change: Decimal | None = None
            ttm_seq_change: Decimal | None = None

            if frequency == FiscalPeriodType.ANNUAL:
                # YoY: Compare against fiscal_year - 1
                if curr_period.fiscal_year is not None and curr_val is not None:
                    prior_fy = curr_period.fiscal_year - 1
                    prior_m = by_fy_fq.get((prior_fy, FiscalPeriodLabel.FY))
                    if (
                        prior_m
                        and prior_m.status == MetricStatus.VALID
                        and prior_m.value is not None
                    ):
                        if prior_m.value > Decimal("0"):
                            yoy_change = (curr_val - prior_m.value) / prior_m.value
                        elif prior_m.value < Decimal("0"):
                            yoy_change = (curr_val - prior_m.value) / abs(prior_m.value)

            elif frequency == FiscalPeriodType.QUARTERLY:
                # QoQ: Compare against immediately preceding quarter in sorted array if valid
                if i > 0 and curr_val is not None:
                    prior_m = sorted_results[i - 1]
                    if (
                        prior_m.status == MetricStatus.VALID
                        and prior_m.value is not None
                    ):
                        if prior_m.value > Decimal("0"):
                            qoq_change = (curr_val - prior_m.value) / prior_m.value
                        elif prior_m.value < Decimal("0"):
                            qoq_change = (curr_val - prior_m.value) / abs(prior_m.value)

                # YoY: Compare against same fiscal quarter of prior fiscal year
                if (
                    curr_period.fiscal_year is not None
                    and curr_period.fiscal_period is not None
                    and curr_val is not None
                ):
                    prior_fy = curr_period.fiscal_year - 1
                    prior_m = by_fy_fq.get((prior_fy, curr_period.fiscal_period))
                    if (
                        prior_m
                        and prior_m.status == MetricStatus.VALID
                        and prior_m.value is not None
                    ):
                        if prior_m.value > Decimal("0"):
                            yoy_change = (curr_val - prior_m.value) / prior_m.value
                        elif prior_m.value < Decimal("0"):
                            yoy_change = (curr_val - prior_m.value) / abs(prior_m.value)

            elif frequency == FiscalPeriodType.TTM and i > 0 and curr_val is not None:
                # TTM Sequential Change: Compare against immediately preceding TTM window in sorted array
                # NEVER label as QoQ!
                prior_m = sorted_results[i - 1]
                if prior_m.status == MetricStatus.VALID and prior_m.value is not None:
                    if prior_m.value > Decimal("0"):
                        ttm_seq_change = (curr_val - prior_m.value) / prior_m.value
                    elif prior_m.value < Decimal("0"):
                        ttm_seq_change = (curr_val - prior_m.value) / abs(prior_m.value)

            points.append(
                TrendPoint(
                    period=curr_period,
                    value=curr_val,
                    status=m.status,
                    qoq_change=qoq_change,
                    yoy_change=yoy_change,
                    ttm_sequential_change=ttm_seq_change,
                    diagnostics=list(m.diagnostics),
                    provenance=m.provenance,
                )
            )

        return points
