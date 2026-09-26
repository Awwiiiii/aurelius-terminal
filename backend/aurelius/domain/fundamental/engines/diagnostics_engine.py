"""
aurelius.domain.fundamental.engines.diagnostics_engine
======================================================
Pure calculation engine for Earnings Quality and Cash Flow Diagnostics:
  - Sloan-Style Balance Sheet Accruals Diagnostic
  - Operating Quality Ratio (OQR = CFO / EBIT) with Multi-Period Persistence

Key Invariants:
  1. Sloan Accruals:
     Formula:
       [(ΔCA - ΔCash) - (ΔCL - ΔSTD) - Depreciation] / Average Total Assets
     Where:
       ΔCA = Current Assets_t - Current Assets_{t-1}
       ΔCash = Cash and Equivalents_t - Cash and Equivalents_{t-1}
       ΔCL = Current Liabilities_t - Current Liabilities_{t-1}
       ΔSTD = Short-Term Debt_t - Short-Term Debt_{t-1}
       Depreciation = Depreciation & Amortization duration fact
     Screening Rule:
       Accruals > +0.10 -> Status: WARNING
       Message: "Requires further investigation: High accruals relative to total assets."
       Under AURELIUS V1 methodology, this measures the magnitude of balance-sheet accruals
       relative to average total assets and can be used as a screening diagnostic for divergence
       between accounting accruals and cash-based activity, without making definitive conclusions.

  2. Operating Quality Ratio (OQR):
     Formula:
       OQR = CFO / EBIT
     Eligibility:
       Evaluated only when EBIT > 0 and CFO is available.
       If EBIT <= 0 -> UNAVAILABLE with NON_POSITIVE_EBIT.
     Threshold:
       OQR < 0.80
     Persistence Sequencing:
       CONSECUTIVE_PERIOD_THRESHOLD = 2
       - 1 period below threshold -> INFORMATIONAL
       - 2 immediately consecutive eligible periods below threshold -> WARNING with
         code: CFO_EBIT_DIVERGENCE_WARNING.
       - Missing, unavailable, or non-positive EBIT periods reset the streak.
       - Consecutive definitions:
           * ANNUAL: consecutive fiscal years.
           * QUARTERLY: consecutive chronological fiscal quarters.
           * TTM: consecutive TTM anchors exactly one quarter apart.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialFact,
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
from aurelius.domain.fundamental.period_matching import (
    MultiPeriodFactStore,
    calculate_two_point_average,
    get_prior_period,
)
from aurelius.domain.fundamental.ttm import TTMWindow


class DiagnosticsEngine:
    """
    Pure calculation engine for quality diagnostics and forensic screening.
    """

    METHODOLOGY_VERSION = "1.0.0"
    SLOAN_ACCRUALS_THRESHOLD = Decimal("0.10")
    OQR_WARNING_THRESHOLD = Decimal("0.80")
    CONSECUTIVE_PERIOD_THRESHOLD = 2

    @classmethod
    def calculate_sloan_accruals(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Sloan Balance-Sheet Accruals:
          [(ΔCA - ΔCash) - (ΔCL - ΔSTD) - Depreciation] / Average Total Assets

        Measures the magnitude of balance-sheet accruals relative to average total assets
        and can be used as a screening diagnostic for divergence between accounting accruals
        and cash-based activity.
        """
        # Average Assets
        avg_assets, a_diag, a_used_fb, asset_facts = calculate_two_point_average(
            CanonicalConcept.TOTAL_ASSETS,
            current_period,
            prior_period,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_fact_ids: list[str] = [f.fact_id for f in asset_facts]
        all_concepts: list[str] = ["TOTAL_ASSETS"]
        all_periods: list[str] = [
            current_period.period_key,
            *([prior_period.period_key] if prior_period else []),
        ]
        all_diags: list[MetricDiagnostic] = [a_diag] if a_diag and not a_used_fb else []

        if prior_period is None:
            return MetricResult(
                metric_id=FundamentalMetricId.SLOAN_ACCRUALS,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_PRIOR_PERIOD,
                        message="Prior period balance sheet is missing for Sloan accruals change computation.",
                        details={"period": current_period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_SLOAN_ACCRUALS",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=[
                        "CURRENT_ASSETS",
                        "CASH_AND_EQUIVALENTS",
                        "CURRENT_LIABILITIES",
                        "TOTAL_ASSETS",
                    ],
                    source_periods=[current_period.period_key],
                ),
            )

        if avg_assets is None or (a_diag is not None and not a_used_fb):
            return MetricResult(
                metric_id=FundamentalMetricId.SLOAN_ACCRUALS,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=all_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_SLOAN_ACCRUALS",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                ),
            )

        if avg_assets <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.SLOAN_ACCRUALS,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_AVERAGE_ASSETS,
                        message="Average Total Assets is zero or negative; Sloan accruals is unavailable.",
                        details={"average_assets": str(avg_assets)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_SLOAN_ACCRUALS",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                ),
            )

        # Delta Current Assets (CA)
        ca_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_ASSETS,
            current_period.period_key,
        )
        ca_prior = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_ASSETS,
            prior_period.period_key,
        )

        # Delta Cash
        cash_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
            current_period.period_key,
        )
        cash_prior = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
            prior_period.period_key,
        )

        # Delta Current Liabilities (CL)
        cl_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_LIABILITIES,
            current_period.period_key,
        )
        cl_prior = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_LIABILITIES,
            prior_period.period_key,
        )

        # Delta Short-Term Debt (STD)
        # Using source facts via SolvencyEngine concept lookup or default 0 if not present
        std_curr_fact = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            [
                "Current Debt",
                "Short Term Debt",
                "Current Portion Of Long Term Debt",
                "Short Term Borrowings",
            ],
            current_period.period_key,
        )
        std_prior_fact = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            [
                "Current Debt",
                "Short Term Debt",
                "Current Portion Of Long Term Debt",
                "Short Term Borrowings",
            ],
            prior_period.period_key,
        )

        # Depreciation (Duration fact from Cash Flow or Income Statement)
        dep_fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            [
                "Depreciation And Amortization",
                "Depreciation Amortization Depletion",
                "Depreciation & Amortization",
            ],
            current_period.period_key,
        )
        if dep_fact is None:
            dep_fact = fact_store.get_source_fact(
                StatementType.INCOME_STATEMENT,
                [
                    "Depreciation And Amortization",
                    "Depreciation Amortization Depletion",
                    "Depreciation & Amortization",
                ],
                current_period.period_key,
            )

        # Check required working capital facts
        missing_facts = []
        if ca_curr is None or ca_prior is None:
            missing_facts.append("CURRENT_ASSETS")
        if cash_curr is None or cash_prior is None:
            missing_facts.append("CASH_AND_EQUIVALENTS")
        if cl_curr is None or cl_prior is None:
            missing_facts.append("CURRENT_LIABILITIES")

        if missing_facts:
            return MetricResult(
                metric_id=FundamentalMetricId.SLOAN_ACCRUALS,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing line item(s) across periods for Sloan accruals: {', '.join(missing_facts)}.",
                        details={"missing_concepts": ", ".join(missing_facts)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_SLOAN_ACCRUALS",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=list(
                        dict.fromkeys([*all_concepts, *missing_facts])
                    ),
                    source_periods=all_periods,
                ),
            )

        # Collect facts for provenance
        contributing_facts = [
            ca_curr,
            ca_prior,
            cash_curr,
            cash_prior,
            cl_curr,
            cl_prior,
        ]
        if std_curr_fact:
            contributing_facts.append(std_curr_fact)
        if std_prior_fact:
            contributing_facts.append(std_prior_fact)
        if dep_fact:
            contributing_facts.append(dep_fact)

        all_fact_ids.extend(f.fact_id for f in contributing_facts)

        delta_ca = ca_curr.value - ca_prior.value
        delta_cash = cash_curr.value - cash_prior.value
        delta_cl = cl_curr.value - cl_prior.value

        std_curr_val = (
            std_curr_fact.value if std_curr_fact is not None else Decimal("0")
        )
        std_prior_val = (
            std_prior_fact.value if std_prior_fact is not None else Decimal("0")
        )
        delta_std = std_curr_val - std_prior_val

        dep_val = abs(dep_fact.value) if dep_fact is not None else Decimal("0")

        accruals_numerator = (delta_ca - delta_cash) - (delta_cl - delta_std) - dep_val
        sloan_val = accruals_numerator / avg_assets

        status = MetricStatus.VALID
        diagnostics: list[MetricDiagnostic] = []

        if sloan_val > cls.SLOAN_ACCRUALS_THRESHOLD:
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.SLOAN_ACCRUALS_WARNING,
                    message="Requires further investigation: High accruals relative to total assets.",
                    details={
                        "sloan_accruals": str(sloan_val),
                        "threshold": str(cls.SLOAN_ACCRUALS_THRESHOLD),
                    },
                )
            )

        return MetricResult(
            metric_id=FundamentalMetricId.SLOAN_ACCRUALS,
            category=MetricCategory.EFFICIENCY,
            status=status,
            value=sloan_val,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_SLOAN_ACCRUALS",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(all_fact_ids)),
                source_concepts=[
                    "CURRENT_ASSETS",
                    "CASH_AND_EQUIVALENTS",
                    "CURRENT_LIABILITIES",
                    "SHORT_TERM_DEBT",
                    "DEPRECIATION",
                    "TOTAL_ASSETS",
                ],
                source_periods=all_periods,
                methodology_notes=(
                    "Sloan Accruals = [(ΔCA - ΔCash) - (ΔCL - ΔSTD) - Dep] / Average Assets. "
                    "Measures the magnitude of balance-sheet accruals relative to average total assets "
                    "and can be used as a screening diagnostic for divergence between accounting accruals "
                    "and cash-based activity."
                ),
            ),
        )

    @classmethod
    def calculate_single_period_oqr(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Operating Quality Ratio (OQR) for a single period: CFO / EBIT.
        Eligible only when EBIT > 0.
        If EBIT <= 0 -> UNAVAILABLE with NON_POSITIVE_EBIT.
        """
        cfo_fact = fact_store.get_canonical_fact(
            StatementType.CASH_FLOW,
            CanonicalConcept.OPERATING_CASH_FLOW,
            period.period_key,
        )
        ebit_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.OPERATING_INCOME,
            period.period_key,
        )

        all_facts = []
        if cfo_fact:
            all_facts.append(cfo_fact.fact_id)
        if ebit_fact:
            all_facts.append(ebit_fact.fact_id)

        if cfo_fact is None or ebit_fact is None:
            missing = []
            if cfo_fact is None:
                missing.append("OPERATING_CASH_FLOW")
            if ebit_fact is None:
                missing.append("OPERATING_INCOME")
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_QUALITY_RATIO,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing line item(s) for OQR: {', '.join(missing)}.",
                        details={
                            "missing_concepts": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_OQR",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_facts,
                    source_concepts=["OPERATING_CASH_FLOW", "OPERATING_INCOME"],
                    source_periods=[period.period_key],
                ),
            )

        if ebit_fact.value <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_QUALITY_RATIO,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_EBIT,
                        message="Operating Income (EBIT) is zero or negative; OQR is uncomputable.",
                        details={
                            "ebit": str(ebit_fact.value),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_OQR",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_facts,
                    source_concepts=["OPERATING_CASH_FLOW", "OPERATING_INCOME"],
                    source_periods=[period.period_key],
                    methodology_notes="OQR requires positive EBIT.",
                ),
            )

        oqr_val = cfo_fact.value / ebit_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.OPERATING_QUALITY_RATIO,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=oqr_val,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_OQR",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_facts,
                source_concepts=["OPERATING_CASH_FLOW", "OPERATING_INCOME"],
                source_periods=[period.period_key],
                methodology_notes="OQR = CFO / EBIT.",
            ),
        )

    @classmethod
    def evaluate_oqr_with_persistence(
        cls,
        current_period: FinancialPeriod,
        all_periods: list[FinancialPeriod],
        frequency: FiscalPeriodType,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Evaluate OQR with multi-period persistence rules:
          Threshold: OQR < 0.80
          Persistence: CONSECUTIVE_PERIOD_THRESHOLD = 2
          - 1 period below threshold -> INFORMATIONAL
          - 2 immediately consecutive eligible periods -> WARNING (CFO_EBIT_DIVERGENCE_WARNING)
          - Missing, unavailable, or non-positive EBIT periods reset the streak.
          - Consecutive checks:
              * ANNUAL: consecutive fiscal years.
              * QUARTERLY: consecutive fiscal quarters.
              * TTM: consecutive TTM anchor windows exactly one quarter apart.
        """
        curr_res = cls.calculate_single_period_oqr(current_period, fact_store)
        if curr_res.status != MetricStatus.VALID or curr_res.value is None:
            return curr_res

        # If current period is >= threshold (>= 0.80), no warning can be triggered
        if curr_res.value >= cls.OQR_WARNING_THRESHOLD:
            return curr_res

        # Current period is < 0.80. Check immediate prior consecutive period.
        prior_period = get_prior_period(current_period, all_periods, frequency)
        if prior_period is None:
            # Only 1 period available; cannot satisfy consecutive threshold of 2
            diag = MetricDiagnostic(
                code=DiagnosticCode.NEGATIVE_EBIT_WARNING,  # informational note
                message="Operating Quality Ratio below 0.80 observed for 1 period; requires 2 consecutive periods for warning.",
                details={
                    "oqr": str(curr_res.value),
                    "period": current_period.period_key,
                },
            )
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_QUALITY_RATIO,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.VALID,
                value=curr_res.value,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[diag],
                provenance=curr_res.provenance,
            )

        prior_res = cls.calculate_single_period_oqr(prior_period, fact_store)

        # Streak check: Prior period must be VALID and < 0.80
        if (
            prior_res.status == MetricStatus.VALID
            and prior_res.value is not None
            and prior_res.value < cls.OQR_WARNING_THRESHOLD
        ):
            # 2 consecutive periods below 0.80!
            warning_diag = MetricDiagnostic(
                code=DiagnosticCode.CFO_EBIT_DIVERGENCE_WARNING,
                message="Requires further investigation: Operating cash flow has lagged EBIT for 2 consecutive periods.",
                details={
                    "current_oqr": str(curr_res.value),
                    "current_period": current_period.period_key,
                    "prior_oqr": str(prior_res.value),
                    "prior_period": prior_period.period_key,
                    "threshold": str(cls.OQR_WARNING_THRESHOLD),
                },
            )
            all_facts = list(
                dict.fromkeys(
                    [
                        *curr_res.provenance.source_fact_ids,
                        *prior_res.provenance.source_fact_ids,
                    ]
                )
            )
            all_periods_keys = list(
                dict.fromkeys(
                    [
                        *curr_res.provenance.source_periods,
                        *prior_res.provenance.source_periods,
                    ]
                )
            )

            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_QUALITY_RATIO,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.VALID,
                value=curr_res.value,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[warning_diag],
                provenance=MetricProvenance(
                    formula_id="FORMULA_OQR_PERSISTENT",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_facts,
                    source_concepts=["OPERATING_CASH_FLOW", "OPERATING_INCOME"],
                    source_periods=all_periods_keys,
                    methodology_notes="OQR < 0.80 persisted across 2 consecutive compatible periods.",
                ),
            )
        else:
            # Prior period was either not below threshold or unavailable/reset
            info_diag = MetricDiagnostic(
                code=DiagnosticCode.NEGATIVE_EBIT_WARNING,
                message="Operating Quality Ratio below 0.80 observed for 1 period; prior consecutive period was not below threshold.",
                details={
                    "current_oqr": str(curr_res.value),
                    "period": current_period.period_key,
                },
            )
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_QUALITY_RATIO,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.VALID,
                value=curr_res.value,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[info_diag],
                provenance=curr_res.provenance,
            )

    @classmethod
    def calculate_sloan_accruals_ttm(
        cls,
        window: TTMWindow,
        prior_anchor: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Sloan Balance-Sheet Accruals for a 4-quarter TTM window:
          [(ΔCA - ΔCash) - (ΔCL - ΔSTD) - Depreciation] / Average Total Assets
        Where:
          - Δ values compare Q(t) (window.anchor_quarter) vs Q(t-4) (prior_anchor)
          - Depreciation is aggregated across all 4 quarters of the TTM window
          - Average Total Assets is the two-point average of Q(t-4) and Q(t)
        """
        current_period = window.anchor_quarter
        all_diags: list[MetricDiagnostic] = []

        if prior_anchor is None and not allow_point_in_time_fallback:
            return MetricResult(
                metric_id=FundamentalMetricId.SLOAN_ACCRUALS,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.INSUFFICIENT_PERIODS_FOR_AVERAGE,
                        message="Beginning anchor quarter Q(t-4) is missing; Sloan accruals is unavailable.",
                        details={"period": current_period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_SLOAN_ACCRUALS_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=[
                        "CURRENT_ASSETS",
                        "CASH_AND_EQUIVALENTS",
                        "CURRENT_LIABILITIES",
                        "TOTAL_ASSETS",
                    ],
                    source_periods=[current_period.period_key],
                ),
            )

        avg_assets, a_diag, a_used_fb, asset_facts = calculate_two_point_average(
            CanonicalConcept.TOTAL_ASSETS,
            current_period,
            prior_anchor,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_fact_ids = [f.fact_id for f in asset_facts]
        all_concepts = ["TOTAL_ASSETS"]
        all_periods = list(
            dict.fromkeys(
                [current_period.period_key, *(f.period.period_key for f in asset_facts)]
            )
        )

        if a_diag is not None:
            all_diags.append(a_diag)

        if avg_assets is None or (a_diag is not None and not a_used_fb):
            return MetricResult(
                metric_id=FundamentalMetricId.SLOAN_ACCRUALS,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=all_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_SLOAN_ACCRUALS_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                ),
            )

        if avg_assets <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.SLOAN_ACCRUALS,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_AVERAGE_ASSETS,
                        message="Average Total Assets is zero or negative; Sloan accruals is unavailable.",
                        details={"average_assets": str(avg_assets)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_SLOAN_ACCRUALS_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                ),
            )

        ca_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_ASSETS,
            current_period.period_key,
        )
        ca_prior = (
            fact_store.get_canonical_fact(
                StatementType.BALANCE_SHEET,
                CanonicalConcept.CURRENT_ASSETS,
                prior_anchor.period_key,
            )
            if prior_anchor
            else (ca_curr if a_used_fb else None)
        )

        cash_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
            current_period.period_key,
        )
        cash_prior = (
            fact_store.get_canonical_fact(
                StatementType.BALANCE_SHEET,
                CanonicalConcept.CASH_AND_EQUIVALENTS,
                prior_anchor.period_key,
            )
            if prior_anchor
            else (cash_curr if a_used_fb else None)
        )

        cl_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_LIABILITIES,
            current_period.period_key,
        )
        cl_prior = (
            fact_store.get_canonical_fact(
                StatementType.BALANCE_SHEET,
                CanonicalConcept.CURRENT_LIABILITIES,
                prior_anchor.period_key,
            )
            if prior_anchor
            else (cl_curr if a_used_fb else None)
        )

        std_curr = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            [
                "Short Term Debt",
                "Current Portion Of Long Term Debt",
                "Short Term Borrowings",
            ],
            current_period.period_key,
        )
        std_prior = (
            fact_store.get_source_fact(
                StatementType.BALANCE_SHEET,
                [
                    "Short Term Debt",
                    "Current Portion Of Long Term Debt",
                    "Short Term Borrowings",
                ],
                prior_anchor.period_key,
            )
            if prior_anchor
            else (std_curr if a_used_fb else None)
        )

        # TTM Depreciation across the 4 quarters of window
        dep_facts: list[FinancialFact] = []
        for q in window.quarters:
            df = fact_store.get_source_fact(
                StatementType.CASH_FLOW,
                [
                    "Depreciation And Amortization",
                    "Depreciation Amortization Depletion",
                    "Depreciation & Amortization",
                ],
                q.period_key,
            )
            if df is None:
                df = fact_store.get_source_fact(
                    StatementType.INCOME_STATEMENT,
                    [
                        "Depreciation And Amortization",
                        "Depreciation Amortization Depletion",
                        "Depreciation & Amortization",
                    ],
                    q.period_key,
                )
            if df is not None:
                dep_facts.append(df)

        missing_facts = []
        if ca_curr is None or ca_prior is None:
            missing_facts.append("CURRENT_ASSETS")
        if cash_curr is None or cash_prior is None:
            missing_facts.append("CASH_AND_EQUIVALENTS")
        if cl_curr is None or cl_prior is None:
            missing_facts.append("CURRENT_LIABILITIES")

        if missing_facts:
            return MetricResult(
                metric_id=FundamentalMetricId.SLOAN_ACCRUALS,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing line item(s) across periods for TTM Sloan accruals: {', '.join(missing_facts)}.",
                        details={"missing_concepts": ", ".join(missing_facts)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_SLOAN_ACCRUALS_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=list(
                        dict.fromkeys([*all_concepts, *missing_facts])
                    ),
                    source_periods=all_periods,
                ),
            )

        delta_ca = ca_curr.value - ca_prior.value
        delta_cash = cash_curr.value - cash_prior.value
        delta_cl = cl_curr.value - cl_prior.value
        std_c_val = std_curr.value if std_curr is not None else Decimal("0")
        std_p_val = std_prior.value if std_prior is not None else Decimal("0")
        delta_std = std_c_val - std_p_val

        dep_val = (
            sum((f.value for f in dep_facts), start=Decimal("0"))
            if len(dep_facts) == 4
            else Decimal("0")
        )

        accruals_numerator = (delta_ca - delta_cash) - (delta_cl - delta_std) - dep_val
        sloan_ratio = accruals_numerator / avg_assets

        for f in (
            ca_curr,
            ca_prior,
            cash_curr,
            cash_prior,
            cl_curr,
            cl_prior,
            std_curr,
            std_prior,
            *dep_facts,
        ):
            if f is not None:
                all_fact_ids.append(f.fact_id)
                all_periods.append(f.period.period_key)

        res_diags = list(all_diags)
        if sloan_ratio > cls.SLOAN_ACCRUALS_THRESHOLD:
            res_diags.append(
                MetricDiagnostic(
                    code=DiagnosticCode.SLOAN_ACCRUALS_WARNING,
                    message="Requires further investigation: High accruals relative to total assets.",
                    details={
                        "sloan_ratio": str(sloan_ratio),
                        "threshold": str(cls.SLOAN_ACCRUALS_THRESHOLD),
                    },
                )
            )

        return MetricResult(
            metric_id=FundamentalMetricId.SLOAN_ACCRUALS,
            category=MetricCategory.EFFICIENCY,
            status=MetricStatus.VALID,
            value=sloan_ratio,
            unit=Unit.RATIO,
            currency=None,
            period=window.ttm_period,
            diagnostics=res_diags,
            provenance=MetricProvenance(
                formula_id="FORMULA_SLOAN_ACCRUALS_TTM",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(all_fact_ids)),
                source_concepts=[
                    "CURRENT_ASSETS",
                    "CASH_AND_EQUIVALENTS",
                    "CURRENT_LIABILITIES",
                    "TOTAL_ASSETS",
                    "DEPRECIATION_AND_AMORTIZATION",
                ],
                source_periods=list(dict.fromkeys(all_periods)),
                methodology_notes="Measures the magnitude of balance-sheet accruals relative to average total assets and can be used as a screening diagnostic for divergence between accounting accruals and cash-based activity.",
            ),
        )
