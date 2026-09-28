"""
aurelius.domain.fundamental.engines.reinvestment
================================================
Pure calculation engine for Reinvestment, Reinvestment Rate, and Fundamental Growth.

Formulas:
  Reinvestment = CapEx - D&A + Delta NWC
  Reinvestment Rate = Reinvestment / NOPAT
  Fundamental Growth (g) = Reinvestment Rate * ROIC

Key Invariants:
  - Sourced strictly via Canonical/Source concepts without hardcoded or smoothed fallbacks.
  - Reinvestment < 0 is VALID with NEGATIVE_REINVESTMENT_OBSERVED diagnostic.
  - NOPAT <= 0 renders Reinvestment Rate DISTORTED with NON_POSITIVE_OPERATING_PROFIT.
  - Reinvestment Rate > 200% (> 2.0) attaches HIGH_REINVESTMENT_WARNING.
  - Double-Negative Distortion: if both Reinvestment Rate < 0 and ROIC < 0,
    Fundamental Growth is DISTORTED with DISTORTED_FUNDAMENTAL_GROWTH (two negatives
    cannot produce sustainable internal economic growth).
  - Retrospective Metric Only: g is explicitly documented as historical fundamental growth rate.
  - Missing facts are NEVER converted to zero; they result in explicit UNAVAILABLE status.
  - Full auditable provenance on every derived result.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    FinancialPeriod,
    StatementType,
    Unit,
)
from aurelius.domain.fundamental.engines.capital_allocation import (
    CapitalAllocationEngine,
)
from aurelius.domain.fundamental.engines.operating_nwc import OperatingNWCEngine
from aurelius.domain.fundamental.engines.roic import ROICEngine
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


class ReinvestmentEngine:
    """
    Engine calculating Reinvestment, Reinvestment Rate, and Retrospective Fundamental Growth.
    """

    METHODOLOGY_VERSION = "1.0.0"

    # -------------------------------------------------------------------------
    # Reinvestment
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_reinvestment(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Operational Reinvestment:
          Reinvestment = CapEx - D&A + Delta NWC
        """
        diagnostics: list[MetricDiagnostic] = []
        missing_components: list[str] = []

        # 1. CapEx
        capex_res = CapitalAllocationEngine.calculate_capex(current_period, fact_store)
        if capex_res.status != MetricStatus.VALID or capex_res.value is None:
            missing_components.append("Capital Expenditures")
            diagnostics.extend(capex_res.diagnostics)

        # 2. D&A (from Cash Flow or Income Statement)
        da_fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            [
                "Depreciation And Amortization",
                "Depreciation Amortization Depletion",
                "Depreciation & Amortization",
            ],
            current_period.period_key,
        )
        if da_fact is None:
            da_fact = fact_store.get_source_fact(
                StatementType.INCOME_STATEMENT,
                [
                    "Depreciation And Amortization",
                    "Depreciation & Amortization",
                ],
                current_period.period_key,
            )

        if da_fact is None:
            missing_components.append("Depreciation & Amortization")
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.MISSING_DEPRECIATION_AMORTIZATION,
                    message="Depreciation & Amortization is absent from both Cash Flow and Income Statement.",
                    details={"period": current_period.period_key},
                )
            )

        # 3. Delta NWC
        delta_nwc_res = OperatingNWCEngine.calculate_delta_nwc(
            current_period, prior_period, fact_store
        )
        if delta_nwc_res.status != MetricStatus.VALID or delta_nwc_res.value is None:
            missing_components.append("Delta NWC")
            diagnostics.extend(delta_nwc_res.diagnostics)

        if missing_components:
            return MetricResult(
                metric_id=FundamentalMetricId.REINVESTMENT,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=capex_res.currency,
                period=current_period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_REINVESTMENT_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=missing_components,
                    source_periods=[current_period.period_key],
                    methodology_notes=f"Missing inputs for Reinvestment: {', '.join(missing_components)}.",
                ),
            )

        assert da_fact is not None
        assert capex_res.value is not None
        assert delta_nwc_res.value is not None
        da_val = abs(da_fact.value)
        # Reinvestment = CapEx - D&A + Delta NWC
        reinvestment_val = capex_res.value - da_val + delta_nwc_res.value

        source_fact_ids = list(
            dict.fromkeys(
                capex_res.provenance.source_fact_ids
                + [da_fact.fact_id]
                + delta_nwc_res.provenance.source_fact_ids
            )
        )
        source_concepts = list(
            dict.fromkeys(
                capex_res.provenance.source_concepts
                + [da_fact.concept.source_concept]
                + delta_nwc_res.provenance.source_concepts
            )
        )
        source_periods = list(
            dict.fromkeys(
                capex_res.provenance.source_periods
                + delta_nwc_res.provenance.source_periods
            )
        )

        # Invariant: Reinvestment < 0 is VALID with NEGATIVE_REINVESTMENT_OBSERVED
        if reinvestment_val < Decimal(0):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.NEGATIVE_REINVESTMENT_OBSERVED,
                    message="Negative reinvestment observed: D&A exceeds CapEx and working capital changes, reflecting net asset shrinkage or working capital liquidation.",
                    details={
                        "reinvestment": str(reinvestment_val),
                        "capex": str(capex_res.value),
                        "dna": str(da_val),
                        "delta_nwc": str(delta_nwc_res.value),
                        "period": current_period.period_key,
                    },
                )
            )

        return MetricResult(
            metric_id=FundamentalMetricId.REINVESTMENT,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=reinvestment_val,
            unit=Unit.CURRENCY,
            currency=capex_res.currency,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_REINVESTMENT_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=source_fact_ids,
                source_concepts=source_concepts,
                source_periods=source_periods,
                methodology_notes=(
                    f"Reinvestment = CapEx ({capex_res.value}) - D&A ({da_val}) "
                    f"+ Delta NWC ({delta_nwc_res.value}) = {reinvestment_val}."
                ),
            ),
        )

    # -------------------------------------------------------------------------
    # Reinvestment Rate
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_reinvestment_rate(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Reinvestment Rate:
          Reinvestment Rate = Reinvestment / NOPAT
        """
        reinv_res = cls.calculate_reinvestment(current_period, prior_period, fact_store)
        nopat_res = ROICEngine.calculate_nopat(current_period, fact_store)

        diagnostics: list[MetricDiagnostic] = list(reinv_res.diagnostics)
        diagnostics.extend(nopat_res.diagnostics)

        all_fact_ids = list(
            dict.fromkeys(
                reinv_res.provenance.source_fact_ids
                + nopat_res.provenance.source_fact_ids
            )
        )
        all_concepts = list(
            dict.fromkeys(
                reinv_res.provenance.source_concepts
                + nopat_res.provenance.source_concepts
            )
        )
        all_periods = list(
            dict.fromkeys(
                reinv_res.provenance.source_periods
                + nopat_res.provenance.source_periods
            )
        )

        # Missing input checks
        if reinv_res.status != MetricStatus.VALID or reinv_res.value is None:
            return MetricResult(
                metric_id=FundamentalMetricId.REINVESTMENT_RATE,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_REINVESTMENT_RATE_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="Reinvestment component unavailable.",
                ),
            )

        if nopat_res.status != MetricStatus.VALID or nopat_res.value is None:
            return MetricResult(
                metric_id=FundamentalMetricId.REINVESTMENT_RATE,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_REINVESTMENT_RATE_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="NOPAT component unavailable.",
                ),
            )

        assert reinv_res.value is not None
        assert nopat_res.value is not None

        # Boundary: NOPAT <= 0 renders Reinvestment Rate DISTORTED
        if nopat_res.value <= Decimal(0):
            distorted_diags = [
                MetricDiagnostic(
                    code=DiagnosticCode.NON_POSITIVE_OPERATING_PROFIT,
                    message="NOPAT is zero or negative; division by non-positive operating profit renders Reinvestment Rate economically meaningless.",
                    details={
                        "nopat": str(nopat_res.value),
                        "period": current_period.period_key,
                    },
                ),
                *diagnostics,
            ]
            return MetricResult(
                metric_id=FundamentalMetricId.REINVESTMENT_RATE,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=distorted_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_REINVESTMENT_RATE_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="NOPAT <= 0 renders Reinvestment Rate economically meaningless.",
                ),
            )

        rate = reinv_res.value / nopat_res.value

        # High Reinvestment Warning (> 200% / > 2.0)
        if rate > Decimal("2.0"):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.HIGH_REINVESTMENT_WARNING,
                    message="Reinvestment rate exceeds 200%: entity is investing substantially more than operating profits, reliant on external capital.",
                    details={
                        "reinvestment_rate": str(rate),
                        "period": current_period.period_key,
                    },
                )
            )

        return MetricResult(
            metric_id=FundamentalMetricId.REINVESTMENT_RATE,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=rate,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_REINVESTMENT_RATE_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_fact_ids,
                source_concepts=all_concepts,
                source_periods=all_periods,
                methodology_notes=(
                    f"Reinvestment Rate = Reinvestment ({reinv_res.value}) / NOPAT ({nopat_res.value}) = {rate}."
                ),
            ),
        )

    # -------------------------------------------------------------------------
    # Fundamental Growth
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_fundamental_growth(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Retrospective Fundamental Growth:
          g = Reinvestment Rate * ROIC
        """
        rate_res = cls.calculate_reinvestment_rate(
            current_period, prior_period, fact_store
        )
        roic_res = ROICEngine.calculate_roic(
            current_period,
            prior_period,
            fact_store,
            allow_point_in_time_fallback=allow_point_in_time_fallback,
        )

        diagnostics: list[MetricDiagnostic] = list(rate_res.diagnostics)
        diagnostics.extend(roic_res.diagnostics)

        all_fact_ids = list(
            dict.fromkeys(
                rate_res.provenance.source_fact_ids
                + roic_res.provenance.source_fact_ids
            )
        )
        all_concepts = list(
            dict.fromkeys(
                rate_res.provenance.source_concepts
                + roic_res.provenance.source_concepts
            )
        )
        all_periods = list(
            dict.fromkeys(
                rate_res.provenance.source_periods + roic_res.provenance.source_periods
            )
        )

        # If rate or roic is unavailable
        if (
            rate_res.status == MetricStatus.UNAVAILABLE
            or roic_res.status == MetricStatus.UNAVAILABLE
        ):
            return MetricResult(
                metric_id=FundamentalMetricId.FUNDAMENTAL_GROWTH,
                category=MetricCategory.GROWTH,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_FUNDAMENTAL_GROWTH_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="Reinvestment Rate or ROIC unavailable for retrospective fundamental growth.",
                ),
            )

        # If rate is DISTORTED (e.g. NOPAT <= 0)
        if rate_res.status == MetricStatus.DISTORTED:
            distorted_diags = [
                MetricDiagnostic(
                    code=DiagnosticCode.DISTORTED_FUNDAMENTAL_GROWTH,
                    message="Fundamental growth rate is distorted because Reinvestment Rate denominator (NOPAT) is non-positive.",
                    details={"period": current_period.period_key},
                ),
                *diagnostics,
            ]
            return MetricResult(
                metric_id=FundamentalMetricId.FUNDAMENTAL_GROWTH,
                category=MetricCategory.GROWTH,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=distorted_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_FUNDAMENTAL_GROWTH_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="Reinvestment Rate is distorted.",
                ),
            )

        if roic_res.status == MetricStatus.DISTORTED or roic_res.value is None:
            distorted_diags = [
                MetricDiagnostic(
                    code=DiagnosticCode.DISTORTED_FUNDAMENTAL_GROWTH,
                    message="Fundamental growth rate is distorted because ROIC is distorted or unavailable.",
                    details={"period": current_period.period_key},
                ),
                *diagnostics,
            ]
            return MetricResult(
                metric_id=FundamentalMetricId.FUNDAMENTAL_GROWTH,
                category=MetricCategory.GROWTH,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=distorted_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_FUNDAMENTAL_GROWTH_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="ROIC is distorted.",
                ),
            )

        rate_val = rate_res.value
        roic_val = roic_res.value
        assert rate_val is not None
        assert roic_val is not None

        # Invariant: Double-Negative Distortion (Rate < 0 AND ROIC < 0)
        # Mathematically produces positive growth, but financially absurd!
        if rate_val < Decimal(0) and roic_val < Decimal(0):
            distorted_diags = [
                MetricDiagnostic(
                    code=DiagnosticCode.DISTORTED_FUNDAMENTAL_GROWTH,
                    message="Double-negative distortion: negative reinvestment rate multiplied by negative ROIC produces mathematically positive but economically invalid growth rate.",
                    details={
                        "reinvestment_rate": str(rate_val),
                        "roic": str(roic_val),
                        "period": current_period.period_key,
                    },
                ),
                *diagnostics,
            ]
            return MetricResult(
                metric_id=FundamentalMetricId.FUNDAMENTAL_GROWTH,
                category=MetricCategory.GROWTH,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=distorted_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_FUNDAMENTAL_GROWTH_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="Double-negative distortion: negative reinvestment and negative ROIC.",
                ),
            )

        growth_val = rate_val * roic_val

        if growth_val < Decimal(0):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.NEGATIVE_FUNDAMENTAL_GROWTH,
                    message="Negative fundamental growth rate observed due to operational contraction or negative capital returns.",
                    details={
                        "fundamental_growth": str(growth_val),
                        "reinvestment_rate": str(rate_val),
                        "roic": str(roic_val),
                        "period": current_period.period_key,
                    },
                )
            )

        return MetricResult(
            metric_id=FundamentalMetricId.FUNDAMENTAL_GROWTH,
            category=MetricCategory.GROWTH,
            status=MetricStatus.VALID,
            value=growth_val,
            unit=Unit.PERCENT,
            currency=None,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_FUNDAMENTAL_GROWTH_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_fact_ids,
                source_concepts=all_concepts,
                source_periods=all_periods,
                methodology_notes=(
                    f"Historical Fundamental Growth = Reinvestment Rate ({rate_val}) * ROIC ({roic_val}) = {growth_val}. "
                    "Retrospective internal metric only, not a forward projection or valuation forecast."
                ),
            ),
        )
