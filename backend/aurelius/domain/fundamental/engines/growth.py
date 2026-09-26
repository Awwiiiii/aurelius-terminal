"""
aurelius.domain.fundamental.engines.growth
==========================================
Pure calculation engine for top-line revenue growth (YoY and QoQ).
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialPeriod,
    FiscalPeriodType,
    StatementType,
    Unit,
)
from aurelius.domain.fundamental.enums import (
    DiagnosticCode,
    FundamentalMetricId,
    MetricCategory,
    MetricStatus,
)
from aurelius.domain.fundamental.models import (
    MetricDiagnostic,
    MetricProvenance,
    MetricResult,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore


class GrowthEngine:
    """
    Engine calculating period-over-period growth metrics.
    """

    @staticmethod
    def calculate_revenue_growth_yoy(
        current_period: FinancialPeriod,
        prior_year_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Year-over-Year Revenue Growth: (Revenue_t - Revenue_t-1) / Revenue_t-1.
        """
        curr_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.REVENUE,
            current_period.period_key,
        )
        if curr_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_YOY,
                category=MetricCategory.GROWTH,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Current period Revenue fact is missing.",
                        details={
                            "concept": "REVENUE",
                            "period": current_period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_YOY",
                    source_concepts=["REVENUE"],
                    source_periods=[current_period.period_key],
                ),
            )

        if prior_year_period is None:
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_YOY,
                category=MetricCategory.GROWTH,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_PRIOR_PERIOD,
                        message="Prior year comparison period is unavailable.",
                        details={"period": current_period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_YOY",
                    source_fact_ids=[curr_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[current_period.period_key],
                ),
            )

        prior_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.REVENUE,
            prior_year_period.period_key,
        )
        if prior_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_YOY,
                category=MetricCategory.GROWTH,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_PRIOR_PERIOD,
                        message=f"Prior year Revenue fact is missing for period {prior_year_period.period_key}.",
                        details={
                            "concept": "REVENUE",
                            "prior_period": prior_year_period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_YOY",
                    source_fact_ids=[curr_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[
                        current_period.period_key,
                        prior_year_period.period_key,
                    ],
                ),
            )

        # Check for zero or negative base revenue
        if prior_fact.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_YOY,
                category=MetricCategory.GROWTH,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Prior year revenue is zero; growth rate cannot be calculated.",
                        details={"prior_value": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_YOY",
                    source_fact_ids=[curr_fact.fact_id, prior_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[
                        prior_year_period.period_key,
                        current_period.period_key,
                    ],
                ),
            )

        if prior_fact.value < Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_YOY,
                category=MetricCategory.GROWTH,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NEGATIVE_BASE_REVENUE,
                        message="Prior year revenue is negative; percentage growth is economically distorted.",
                        details={"prior_value": str(prior_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_YOY",
                    source_fact_ids=[curr_fact.fact_id, prior_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[
                        prior_year_period.period_key,
                        current_period.period_key,
                    ],
                ),
            )

        growth_val = (curr_fact.value - prior_fact.value) / prior_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.REVENUE_GROWTH_YOY,
            category=MetricCategory.GROWTH,
            status=MetricStatus.VALID,
            value=growth_val,
            unit=Unit.PERCENT,
            currency=None,
            period=current_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_REVENUE_GROWTH_YOY",
                source_fact_ids=[curr_fact.fact_id, prior_fact.fact_id],
                source_concepts=["REVENUE"],
                source_periods=[
                    prior_year_period.period_key,
                    current_period.period_key,
                ],
                methodology_notes="YoY growth computed over prior year matching period.",
            ),
        )

    @staticmethod
    def calculate_revenue_growth_qoq(
        current_period: FinancialPeriod,
        prior_quarter_period: FinancialPeriod | None,
        frequency: FiscalPeriodType,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Quarter-over-Quarter Revenue Growth: (Revenue_Qt - Revenue_Qt-1) / Revenue_Qt-1.
        Only valid for QUARTERLY frequency.
        """
        if frequency != FiscalPeriodType.QUARTERLY:
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_QOQ,
                category=MetricCategory.GROWTH,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.PERIOD_ALIGNMENT_MISMATCH,
                        message="QoQ growth is only applicable to QUARTERLY statement reporting.",
                        details={"frequency": frequency.value},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_QOQ",
                    source_concepts=["REVENUE"],
                    source_periods=[current_period.period_key],
                ),
            )

        curr_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.REVENUE,
            current_period.period_key,
        )
        if curr_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_QOQ,
                category=MetricCategory.GROWTH,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Current quarter Revenue fact is missing.",
                        details={
                            "concept": "REVENUE",
                            "period": current_period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_QOQ",
                    source_concepts=["REVENUE"],
                    source_periods=[current_period.period_key],
                ),
            )

        if prior_quarter_period is None:
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_QOQ,
                category=MetricCategory.GROWTH,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_PRIOR_PERIOD,
                        message="Prior sequential quarter is unavailable.",
                        details={"period": current_period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_QOQ",
                    source_fact_ids=[curr_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[current_period.period_key],
                ),
            )

        prior_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.REVENUE,
            prior_quarter_period.period_key,
        )
        if prior_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_QOQ,
                category=MetricCategory.GROWTH,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_PRIOR_PERIOD,
                        message=f"Prior quarter Revenue fact is missing for {prior_quarter_period.period_key}.",
                        details={
                            "concept": "REVENUE",
                            "prior_period": prior_quarter_period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_QOQ",
                    source_fact_ids=[curr_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[
                        prior_quarter_period.period_key,
                        current_period.period_key,
                    ],
                ),
            )

        if prior_fact.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_QOQ,
                category=MetricCategory.GROWTH,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Prior quarter revenue is zero; growth cannot be calculated.",
                        details={"prior_value": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_QOQ",
                    source_fact_ids=[curr_fact.fact_id, prior_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[
                        prior_quarter_period.period_key,
                        current_period.period_key,
                    ],
                ),
            )

        if prior_fact.value < Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.REVENUE_GROWTH_QOQ,
                category=MetricCategory.GROWTH,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NEGATIVE_BASE_REVENUE,
                        message="Prior quarter revenue is negative; growth cannot be calculated meaningfully.",
                        details={"prior_value": str(prior_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_REVENUE_GROWTH_QOQ",
                    source_fact_ids=[curr_fact.fact_id, prior_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[
                        prior_quarter_period.period_key,
                        current_period.period_key,
                    ],
                ),
            )

        qoq_val = (curr_fact.value - prior_fact.value) / prior_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.REVENUE_GROWTH_QOQ,
            category=MetricCategory.GROWTH,
            status=MetricStatus.VALID,
            value=qoq_val,
            unit=Unit.PERCENT,
            currency=None,
            period=current_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_REVENUE_GROWTH_QOQ",
                source_fact_ids=[curr_fact.fact_id, prior_fact.fact_id],
                source_concepts=["REVENUE"],
                source_periods=[
                    prior_quarter_period.period_key,
                    current_period.period_key,
                ],
                methodology_notes="QoQ growth computed over sequential prior quarter.",
            ),
        )
