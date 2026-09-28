"""
aurelius.domain.fundamental.engines.credit
==========================================
Pure calculation engine for Fundamental Credit Diagnostics:
1. Piotroski F-Score (Canonical 9 Signals)
2. Altman Z-Score (Structural Dual-Model Architecture)

Key Invariants:
  - Canonical Piotroski F5: Sourced strictly via Long-Term Debt relative to 2-point
    Average Total Assets (Piotroski 2000). Never uses Gross Debt or ending assets.
  - Piotroski Tie Conventions:
      * ZERO_LONG_TERM_DEBT_PASS_CONVENTION: Unleveraged firms (LTD_t == 0 and LTD_t-1 == 0)
        pass F5 to avoid penalizing debt-free capital structures.
      * UNCHANGED_POSITIVE_LEVERAGE_FAIL: Positive unchanged leverage fails F5 under canonical
        strict inequality.
  - Partial Score Presentation: Raw pass count, evaluated count, total (9), coverage ratio.
    Normalized 9-point equivalent scores are strictly prohibited.
  - Altman Structural Dispatch: Dispatched by structural balance-sheet heuristics
    (Inventory/TA >= 5% AND Net PPE/TA >= 15%), NEVER by vendor sector/industry strings.
  - Unclassified balance sheets (banks, insurers) are NOT_APPLICABLE (FINANCIAL_ENTITY_EXEMPTION).
  - Borderline/incomplete asset intensity defaults to Model 2 (Z'') under explicit methodology choice.
  - Full auditable provenance and diagnostics.
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialPeriod,
    FiscalPeriodLabel,
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
    get_prior_period,
)


class PiotroskiSignalResult(BaseModel):
    """
    Individual evaluation for one of the 9 Piotroski signals.
    """

    model_config = ConfigDict(frozen=True)

    signal_id: str
    status: str
    raw_value: Decimal | None = None
    comparison_value: Decimal | None = None
    notes: str = ""


class PiotroskiResult(BaseModel):
    """
    Aggregate Piotroski F-Score evaluation with tri-state coverage accounting.
    """

    model_config = ConfigDict(frozen=True)

    raw_pass_count: int
    evaluated_signal_count: int
    total_signal_count: int = 9
    coverage_ratio: Decimal
    status: MetricStatus
    metric_result: MetricResult
    signals: list[PiotroskiSignalResult]


class AltmanZScoreResult(BaseModel):
    """
    Altman Z-Score evaluation including model dispatch and zone classification.
    """

    model_config = ConfigDict(frozen=True)

    dispatched_model: Literal[
        "MODEL_1_MANUFACTURING", "MODEL_2_SERVICE", "EXEMPT_FINANCIAL"
    ]
    dispatch_rationale: str
    coefficients: dict[str, Decimal]
    factors: dict[str, Decimal]
    total_score: Decimal | None
    zone: Literal["SAFE", "GREY", "DISTRESS"] | None
    metric_result: MetricResult


class FundamentalCreditEngine:
    """
    Engine calculating Piotroski F-Score and Altman Z-Score.
    """

    METHODOLOGY_VERSION = "1.0.0"

    # =========================================================================
    # Piotroski F-Score (9 Signals)
    # =========================================================================

    @classmethod
    def calculate_piotroski_f_score(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        prior_prior_period: FinancialPeriod | None = None,
    ) -> PiotroskiResult:
        """
        Calculate Piotroski 9-Signal F-Score with strict tri-state coverage accounting.
        """
        signals: list[PiotroskiSignalResult] = []
        diagnostics: list[MetricDiagnostic] = []
        source_fact_ids: list[str] = []
        source_concepts: list[str] = []
        source_periods: list[str] = [current_period.period_key]

        if prior_period is not None:
            source_periods.append(prior_period.period_key)

        # Attempt to auto-resolve prior_prior_period if needed for F5
        if prior_prior_period is None and prior_period is not None:
            all_known_periods = list({f.period for f in fact_store._all_facts})
            freq = (
                FiscalPeriodType.ANNUAL
                if (
                    current_period.fiscal_period == FiscalPeriodLabel.FY
                    or current_period.fiscal_period is None
                )
                else FiscalPeriodType.QUARTERLY
            )
            prior_prior_period = get_prior_period(prior_period, all_known_periods, freq)

        if prior_prior_period is not None:
            source_periods.append(prior_prior_period.period_key)

        # ---------------------------------------------------------------------
        # F1: Positive Net Income (ROA_t > 0)
        # ---------------------------------------------------------------------
        ni_curr = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.NET_INCOME,
            current_period.period_key,
        )
        ta_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.TOTAL_ASSETS,
            current_period.period_key,
        )

        if ni_curr is not None and ta_curr is not None and ta_curr.value > Decimal(0):
            source_fact_ids.extend([ni_curr.fact_id, ta_curr.fact_id])
            source_concepts.extend(["NET_INCOME", "TOTAL_ASSETS"])
            roa_curr = ni_curr.value / ta_curr.value
            f1_status = "PASS" if roa_curr > Decimal(0) else "FAIL"
            signals.append(
                PiotroskiSignalResult(
                    signal_id="F1_ROA",
                    status=f1_status,
                    raw_value=roa_curr,
                    comparison_value=Decimal(0),
                    notes=f"ROA = Net Income ({ni_curr.value}) / Total Assets ({ta_curr.value}) = {roa_curr}.",
                )
            )
        else:
            signals.append(
                PiotroskiSignalResult(
                    signal_id="F1_ROA",
                    status="UNAVAILABLE",
                    notes="Net Income or Total Assets missing for current period.",
                )
            )

        # ---------------------------------------------------------------------
        # F2: Positive Operating Cash Flow (CFO_t > 0)
        # ---------------------------------------------------------------------
        cfo_curr = fact_store.get_canonical_fact(
            StatementType.CASH_FLOW,
            CanonicalConcept.OPERATING_CASH_FLOW,
            current_period.period_key,
        )
        if cfo_curr is not None:
            source_fact_ids.append(cfo_curr.fact_id)
            source_concepts.append("OPERATING_CASH_FLOW")
            f2_status = "PASS" if cfo_curr.value > Decimal(0) else "FAIL"
            signals.append(
                PiotroskiSignalResult(
                    signal_id="F2_CFO",
                    status=f2_status,
                    raw_value=cfo_curr.value,
                    comparison_value=Decimal(0),
                    notes=f"Operating Cash Flow = {cfo_curr.value}.",
                )
            )
        else:
            signals.append(
                PiotroskiSignalResult(
                    signal_id="F2_CFO",
                    status="UNAVAILABLE",
                    notes="Operating Cash Flow missing for current period.",
                )
            )

        # ---------------------------------------------------------------------
        # F3: Accruals Quality (CFO_t > Net Income_t)
        # ---------------------------------------------------------------------
        if cfo_curr is not None and ni_curr is not None:
            f3_status = "PASS" if cfo_curr.value > ni_curr.value else "FAIL"
            signals.append(
                PiotroskiSignalResult(
                    signal_id="F3_ACCRUAL",
                    status=f3_status,
                    raw_value=cfo_curr.value,
                    comparison_value=ni_curr.value,
                    notes=f"CFO ({cfo_curr.value}) vs Net Income ({ni_curr.value}).",
                )
            )
        else:
            signals.append(
                PiotroskiSignalResult(
                    signal_id="F3_ACCRUAL",
                    status="UNAVAILABLE",
                    notes="CFO or Net Income missing for current period.",
                )
            )

        # ---------------------------------------------------------------------
        # F4: Quality of Earnings (ROA_t > ROA_t-1)
        # ---------------------------------------------------------------------
        if prior_period is not None:
            ni_prior = fact_store.get_canonical_fact(
                StatementType.INCOME_STATEMENT,
                CanonicalConcept.NET_INCOME,
                prior_period.period_key,
            )
            ta_prior = fact_store.get_canonical_fact(
                StatementType.BALANCE_SHEET,
                CanonicalConcept.TOTAL_ASSETS,
                prior_period.period_key,
            )
            if (
                ni_curr is not None
                and ta_curr is not None
                and ta_curr.value > Decimal(0)
                and ni_prior is not None
                and ta_prior is not None
                and ta_prior.value > Decimal(0)
            ):
                source_fact_ids.extend([ni_prior.fact_id, ta_prior.fact_id])
                source_concepts.extend(["NET_INCOME", "TOTAL_ASSETS"])
                roa_curr = ni_curr.value / ta_curr.value
                roa_prior = ni_prior.value / ta_prior.value
                f4_status = "PASS" if roa_curr > roa_prior else "FAIL"
                signals.append(
                    PiotroskiSignalResult(
                        signal_id="F4_DELTA_ROA",
                        status=f4_status,
                        raw_value=roa_curr,
                        comparison_value=roa_prior,
                        notes=f"ROA_t ({roa_curr}) vs ROA_t-1 ({roa_prior}).",
                    )
                )
            else:
                signals.append(
                    PiotroskiSignalResult(
                        signal_id="F4_DELTA_ROA",
                        status="UNAVAILABLE",
                        notes="ROA inputs missing for current or prior period.",
                    )
                )
        else:
            signals.append(
                PiotroskiSignalResult(
                    signal_id="F4_DELTA_ROA",
                    status="UNAVAILABLE",
                    notes="Prior consecutive period missing.",
                )
            )

        # ---------------------------------------------------------------------
        # F5: Canonical Long-Term Debt De-leveraging (LTD / Avg Assets)
        # ---------------------------------------------------------------------
        f5_result = cls._evaluate_signal_f5(
            current_period, prior_period, prior_prior_period, fact_store
        )
        signals.append(f5_result)
        if (
            f5_result.status == "PASS"
            and "ZERO_LONG_TERM_DEBT_PASS_CONVENTION" in f5_result.notes
        ):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.ZERO_LONG_TERM_DEBT_PASS_CONVENTION,
                    message="Firm maintains zero long-term debt across both comparison periods; awarded pass under AURELIUS zero-debt convention.",
                    details={"period": current_period.period_key},
                )
            )
        elif (
            f5_result.status == "FAIL"
            and "UNCHANGED_POSITIVE_LEVERAGE_FAIL" in f5_result.notes
        ):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.UNCHANGED_POSITIVE_LEVERAGE_FAIL,
                    message="Canonical Piotroski behavior: positive leverage ratio did not decrease; awarded 0 points.",
                    details={"period": current_period.period_key},
                )
            )

        # ---------------------------------------------------------------------
        # F6: Liquidity Improvement (Current Ratio_t > Current Ratio_t-1)
        # ---------------------------------------------------------------------
        ca_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_ASSETS,
            current_period.period_key,
        )
        cl_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_LIABILITIES,
            current_period.period_key,
        )
        if prior_period is not None:
            ca_prior = fact_store.get_canonical_fact(
                StatementType.BALANCE_SHEET,
                CanonicalConcept.CURRENT_ASSETS,
                prior_period.period_key,
            )
            cl_prior = fact_store.get_canonical_fact(
                StatementType.BALANCE_SHEET,
                CanonicalConcept.CURRENT_LIABILITIES,
                prior_period.period_key,
            )
            if (
                ca_curr is not None
                and cl_curr is not None
                and cl_curr.value > Decimal(0)
                and ca_prior is not None
                and cl_prior is not None
                and cl_prior.value > Decimal(0)
            ):
                source_fact_ids.extend(
                    [
                        ca_curr.fact_id,
                        cl_curr.fact_id,
                        ca_prior.fact_id,
                        cl_prior.fact_id,
                    ]
                )
                source_concepts.extend(["CURRENT_ASSETS", "CURRENT_LIABILITIES"])
                cr_curr = ca_curr.value / cl_curr.value
                cr_prior = ca_prior.value / cl_prior.value
                f6_status = "PASS" if cr_curr > cr_prior else "FAIL"
                signals.append(
                    PiotroskiSignalResult(
                        signal_id="F6_DELTA_LIQUID",
                        status=f6_status,
                        raw_value=cr_curr,
                        comparison_value=cr_prior,
                        notes=f"Current Ratio_t ({cr_curr}) vs Current Ratio_t-1 ({cr_prior}).",
                    )
                )
            else:
                signals.append(
                    PiotroskiSignalResult(
                        signal_id="F6_DELTA_LIQUID",
                        status="UNAVAILABLE",
                        notes="Working capital components missing or non-positive liabilities for current or prior period.",
                    )
                )
        else:
            signals.append(
                PiotroskiSignalResult(
                    signal_id="F6_DELTA_LIQUID",
                    status="UNAVAILABLE",
                    notes="Prior consecutive period missing.",
                )
            )

        # ---------------------------------------------------------------------
        # F7: No Dilution (Shares_t <= Shares_t-1 or Stock Issued <= 0)
        # ---------------------------------------------------------------------
        f7_result = cls._evaluate_signal_f7(current_period, prior_period, fact_store)
        signals.append(f7_result)

        # ---------------------------------------------------------------------
        # F8: Margin Expansion (Gross Margin_t > Gross Margin_t-1)
        # ---------------------------------------------------------------------
        gp_curr = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.GROSS_PROFIT,
            current_period.period_key,
        )
        rev_curr = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.REVENUE,
            current_period.period_key,
        )
        if prior_period is not None:
            gp_prior = fact_store.get_canonical_fact(
                StatementType.INCOME_STATEMENT,
                CanonicalConcept.GROSS_PROFIT,
                prior_period.period_key,
            )
            rev_prior = fact_store.get_canonical_fact(
                StatementType.INCOME_STATEMENT,
                CanonicalConcept.REVENUE,
                prior_period.period_key,
            )
            if (
                gp_curr is not None
                and rev_curr is not None
                and rev_curr.value > Decimal(0)
                and gp_prior is not None
                and rev_prior is not None
                and rev_prior.value > Decimal(0)
            ):
                source_fact_ids.extend(
                    [
                        gp_curr.fact_id,
                        rev_curr.fact_id,
                        gp_prior.fact_id,
                        rev_prior.fact_id,
                    ]
                )
                source_concepts.extend(["GROSS_PROFIT", "REVENUE"])
                gm_curr = gp_curr.value / rev_curr.value
                gm_prior = gp_prior.value / rev_prior.value
                f8_status = "PASS" if gm_curr > gm_prior else "FAIL"
                signals.append(
                    PiotroskiSignalResult(
                        signal_id="F8_DELTA_MARGIN",
                        status=f8_status,
                        raw_value=gm_curr,
                        comparison_value=gm_prior,
                        notes=f"Gross Margin_t ({gm_curr}) vs Gross Margin_t-1 ({gm_prior}).",
                    )
                )
            else:
                signals.append(
                    PiotroskiSignalResult(
                        signal_id="F8_DELTA_MARGIN",
                        status="UNAVAILABLE",
                        notes="Gross profit or revenue missing/non-positive for current or prior period.",
                    )
                )
        else:
            signals.append(
                PiotroskiSignalResult(
                    signal_id="F8_DELTA_MARGIN",
                    status="UNAVAILABLE",
                    notes="Prior consecutive period missing.",
                )
            )

        # ---------------------------------------------------------------------
        # F9: Productivity Gain (Asset Turnover_t > Asset Turnover_t-1)
        # ---------------------------------------------------------------------
        if prior_period is not None:
            if (
                rev_curr is not None
                and ta_curr is not None
                and ta_curr.value > Decimal(0)
                and rev_prior is not None
                and ta_prior is not None
                and ta_prior.value > Decimal(0)
            ):
                source_fact_ids.extend(
                    [
                        rev_curr.fact_id,
                        ta_curr.fact_id,
                        rev_prior.fact_id,
                        ta_prior.fact_id,
                    ]
                )
                source_concepts.extend(["REVENUE", "TOTAL_ASSETS"])
                at_curr = rev_curr.value / ta_curr.value
                at_prior = rev_prior.value / ta_prior.value
                f9_status = "PASS" if at_curr > at_prior else "FAIL"
                signals.append(
                    PiotroskiSignalResult(
                        signal_id="F9_DELTA_TURNOVER",
                        status=f9_status,
                        raw_value=at_curr,
                        comparison_value=at_prior,
                        notes=f"Asset Turnover_t ({at_curr}) vs Asset Turnover_t-1 ({at_prior}).",
                    )
                )
            else:
                signals.append(
                    PiotroskiSignalResult(
                        signal_id="F9_DELTA_TURNOVER",
                        status="UNAVAILABLE",
                        notes="Revenue or total assets missing/non-positive for current or prior period.",
                    )
                )
        else:
            signals.append(
                PiotroskiSignalResult(
                    signal_id="F9_DELTA_TURNOVER",
                    status="UNAVAILABLE",
                    notes="Prior consecutive period missing.",
                )
            )

        # ---------------------------------------------------------------------
        # Aggregate Accounting & Tri-State Reporting
        # ---------------------------------------------------------------------
        raw_pass_count = sum(1 for s in signals if s.status == "PASS")
        evaluated_signal_count = sum(1 for s in signals if s.status in ("PASS", "FAIL"))
        total_signal_count = 9
        coverage_ratio = Decimal(evaluated_signal_count) / Decimal(total_signal_count)

        if evaluated_signal_count == 9:
            status = MetricStatus.VALID
        elif evaluated_signal_count in (7, 8):
            status = MetricStatus.VALID
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.PARTIAL_PIOTROSKI_SCORE_REPORTED,
                    message=f"Partial Piotroski F-score reported ({evaluated_signal_count}/9 signals evaluated, coverage {coverage_ratio:.1%}).",
                    details={
                        "raw_pass_count": str(raw_pass_count),
                        "evaluated_signals": str(evaluated_signal_count),
                        "coverage_ratio": str(coverage_ratio),
                        "period": current_period.period_key,
                    },
                )
            )
        else:
            status = MetricStatus.UNAVAILABLE
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.INSUFFICIENT_PIOTROSKI_SIGNALS,
                    message=f"Insufficient signals ({evaluated_signal_count}/9) to compute reliable Piotroski F-Score (minimum 7 required).",
                    details={
                        "evaluated_signals": str(evaluated_signal_count),
                        "coverage_ratio": str(coverage_ratio),
                        "period": current_period.period_key,
                    },
                )
            )

        metric_result = MetricResult(
            metric_id=FundamentalMetricId.PIOTROSKI_F_SCORE,
            category=MetricCategory.SOLVENCY,
            status=status,
            value=Decimal(raw_pass_count) if status == MetricStatus.VALID else None,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_PIOTROSKI_F_SCORE_CANONICAL_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(source_fact_ids)),
                source_concepts=list(dict.fromkeys(source_concepts)),
                source_periods=list(dict.fromkeys(source_periods)),
                methodology_notes=(
                    f"Canonical Piotroski F-Score (Piotroski 2000): Raw Pass Count = {raw_pass_count} "
                    f"| Evaluated: {evaluated_signal_count} / {total_signal_count} "
                    f"| Coverage: {coverage_ratio:.1%}. Normalized 9-point scaling is strictly forbidden."
                ),
            ),
        )

        return PiotroskiResult(
            raw_pass_count=raw_pass_count,
            evaluated_signal_count=evaluated_signal_count,
            total_signal_count=total_signal_count,
            coverage_ratio=coverage_ratio,
            status=status,
            metric_result=metric_result,
            signals=signals,
        )

    @classmethod
    def _evaluate_signal_f5(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        prior_prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
    ) -> PiotroskiSignalResult:
        """
        Evaluate Canonical Piotroski Signal F5 (Long-Term Debt / Average Assets):
          LEVER_t = LTD_t / ((TA_t-1 + TA_t) / 2)
          LEVER_t-1 = LTD_t-1 / ((TA_t-2 + TA_t-1) / 2)
          F5 passes if LEVER_t < LEVER_t-1.
        """
        if prior_period is None:
            return PiotroskiSignalResult(
                signal_id="F5_DELTA_LEVER",
                status="UNAVAILABLE",
                notes="Prior consecutive period missing.",
            )

        # 1. Long-Term Debt
        ltd_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.LONG_TERM_DEBT,
            current_period.period_key,
        )
        if ltd_curr is None:
            ltd_curr = fact_store.get_source_fact(
                StatementType.BALANCE_SHEET,
                [
                    "Long Term Debt",
                    "Long Term Debt And Capital Lease Obligation",
                    "Long-Term Debt",
                ],
                current_period.period_key,
            )

        ltd_prior = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.LONG_TERM_DEBT,
            prior_period.period_key,
        )
        if ltd_prior is None:
            ltd_prior = fact_store.get_source_fact(
                StatementType.BALANCE_SHEET,
                [
                    "Long Term Debt",
                    "Long Term Debt And Capital Lease Obligation",
                    "Long-Term Debt",
                ],
                prior_period.period_key,
            )

        # 2. Total Assets
        ta_curr = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.TOTAL_ASSETS,
            current_period.period_key,
        )
        ta_prior = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.TOTAL_ASSETS,
            prior_period.period_key,
        )

        # Zero-Debt Invariant: If both periods explicitly report zero LTD, award PASS
        if (
            ltd_curr is not None
            and ltd_prior is not None
            and ltd_curr.value == Decimal(0)
            and ltd_prior.value == Decimal(0)
        ):
            return PiotroskiSignalResult(
                signal_id="F5_DELTA_LEVER",
                status="PASS",
                raw_value=Decimal(0),
                comparison_value=Decimal(0),
                notes="ZERO_LONG_TERM_DEBT_PASS_CONVENTION: Zero long-term debt across both comparison periods.",
            )

        if ltd_curr is None or ltd_prior is None:
            return PiotroskiSignalResult(
                signal_id="F5_DELTA_LEVER",
                status="UNAVAILABLE",
                notes="Long-term debt fact missing for current or prior period.",
            )

        if ta_curr is None or ta_prior is None:
            return PiotroskiSignalResult(
                signal_id="F5_DELTA_LEVER",
                status="UNAVAILABLE",
                notes="Total assets missing for current or prior period.",
            )

        avg_ta_curr = (ta_curr.value + ta_prior.value) / Decimal("2")
        if avg_ta_curr <= Decimal(0):
            return PiotroskiSignalResult(
                signal_id="F5_DELTA_LEVER",
                status="UNAVAILABLE",
                notes="Average total assets for current period is non-positive.",
            )

        lever_curr = ltd_curr.value / avg_ta_curr

        # Need prior-prior Total Assets for LEVER_t-1
        if prior_prior_period is None:
            return PiotroskiSignalResult(
                signal_id="F5_DELTA_LEVER",
                status="UNAVAILABLE",
                raw_value=lever_curr,
                notes="Prior-prior period missing for canonical 2-point average assets in prior period.",
            )

        ta_prior_prior = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.TOTAL_ASSETS,
            prior_prior_period.period_key,
        )
        if ta_prior_prior is None:
            return PiotroskiSignalResult(
                signal_id="F5_DELTA_LEVER",
                status="UNAVAILABLE",
                raw_value=lever_curr,
                notes="Total assets missing for prior-prior period (t-2).",
            )

        avg_ta_prior = (ta_prior.value + ta_prior_prior.value) / Decimal("2")
        if avg_ta_prior <= Decimal(0):
            return PiotroskiSignalResult(
                signal_id="F5_DELTA_LEVER",
                status="UNAVAILABLE",
                notes="Average total assets for prior period is non-positive.",
            )

        lever_prior = ltd_prior.value / avg_ta_prior

        # Evaluation
        if lever_curr < lever_prior:
            return PiotroskiSignalResult(
                signal_id="F5_DELTA_LEVER",
                status="PASS",
                raw_value=lever_curr,
                comparison_value=lever_prior,
                notes=f"Canonical LTD leverage decreased from {lever_prior} to {lever_curr}.",
            )
        elif lever_curr == lever_prior:
            if ltd_curr.value == Decimal(0):
                return PiotroskiSignalResult(
                    signal_id="F5_DELTA_LEVER",
                    status="PASS",
                    raw_value=lever_curr,
                    comparison_value=lever_prior,
                    notes="ZERO_LONG_TERM_DEBT_PASS_CONVENTION: Zero long-term debt across both comparison periods.",
                )
            else:
                return PiotroskiSignalResult(
                    signal_id="F5_DELTA_LEVER",
                    status="FAIL",
                    raw_value=lever_curr,
                    comparison_value=lever_prior,
                    notes="UNCHANGED_POSITIVE_LEVERAGE_FAIL: Leverage ratio remained unchanged at positive level.",
                )
        else:
            return PiotroskiSignalResult(
                signal_id="F5_DELTA_LEVER",
                status="FAIL",
                raw_value=lever_curr,
                comparison_value=lever_prior,
                notes=f"Canonical LTD leverage increased from {lever_prior} to {lever_curr}.",
            )

    @classmethod
    def _evaluate_signal_f7(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
    ) -> PiotroskiSignalResult:
        """
        Evaluate Piotroski Signal F7 (No Dilution):
          Shares_t <= Shares_t-1 (or Cash Flow Stock Issuance <= 0).
        """
        if prior_period is None:
            return PiotroskiSignalResult(
                signal_id="F7_DILUTION",
                status="UNAVAILABLE",
                notes="Prior consecutive period missing.",
            )

        # 1. Try share count lines
        candidate_share_names = [
            "Diluted Average Shares",
            "Basic Average Shares",
            "Ordinary Shares Number",
            "Common Stock Shares Outstanding",
            "Share Issued",
        ]
        sh_curr = fact_store.get_source_fact(
            StatementType.INCOME_STATEMENT,
            candidate_share_names,
            current_period.period_key,
        )
        if sh_curr is None:
            sh_curr = fact_store.get_source_fact(
                StatementType.BALANCE_SHEET,
                candidate_share_names,
                current_period.period_key,
            )

        sh_prior = fact_store.get_source_fact(
            StatementType.INCOME_STATEMENT,
            candidate_share_names,
            prior_period.period_key,
        )
        if sh_prior is None:
            sh_prior = fact_store.get_source_fact(
                StatementType.BALANCE_SHEET,
                candidate_share_names,
                prior_period.period_key,
            )

        if sh_curr is not None and sh_prior is not None and sh_prior.value > Decimal(0):
            f7_status = "PASS" if sh_curr.value <= sh_prior.value else "FAIL"
            return PiotroskiSignalResult(
                signal_id="F7_DILUTION",
                status=f7_status,
                raw_value=sh_curr.value,
                comparison_value=sh_prior.value,
                notes=f"Shares_t ({sh_curr.value}) vs Shares_t-1 ({sh_prior.value}).",
            )

        # 2. Fallback: inspect Cash Flow stock issuance in current period
        issuance_fact = fact_store.get_source_fact(
            StatementType.CASH_FLOW,
            ["Issuance Of Capital Stock", "Common Stock Issuance", "Issuance Of Stock"],
            current_period.period_key,
        )
        if issuance_fact is not None:
            f7_status = "PASS" if issuance_fact.value <= Decimal(0) else "FAIL"
            return PiotroskiSignalResult(
                signal_id="F7_DILUTION",
                status=f7_status,
                raw_value=issuance_fact.value,
                comparison_value=Decimal(0),
                notes=f"Evaluated via Cash Flow stock issuance ({issuance_fact.value}).",
            )

        return PiotroskiSignalResult(
            signal_id="F7_DILUTION",
            status="UNAVAILABLE",
            notes="Shares outstanding and stock issuance facts unavailable.",
        )

    # =========================================================================
    # Altman Z-Score (Dual-Model Architecture)
    # =========================================================================

    @classmethod
    def calculate_altman_z_score(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
        market_cap: Decimal | None,
        altman_model_override: str | None = None,
    ) -> AltmanZScoreResult:
        """
        Calculate Altman Z-Score using structural dual-model dispatch.
        """
        diagnostics: list[MetricDiagnostic] = []
        source_fact_ids: list[str] = []
        source_concepts: list[str] = []

        # 1. Check for unclassified balance sheet (financial institutions / banks / insurers)
        ca_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_ASSETS,
            period.period_key,
        )
        cl_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_LIABILITIES,
            period.period_key,
        )
        ta_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.TOTAL_ASSETS,
            period.period_key,
        )

        if ca_fact is None and cl_fact is None:
            # Unclassified balance sheet -> NOT_APPLICABLE
            diag = MetricDiagnostic(
                code=DiagnosticCode.FINANCIAL_ENTITY_EXEMPTION,
                message="Financial institutions operate under statutory regulatory capital regimes; standard Altman Z-score models are analytically invalid.",
                details={"period": period.period_key},
            )
            unavailable_res = MetricResult(
                metric_id=FundamentalMetricId.ALTMAN_Z_SCORE,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[diag],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ALTMAN_Z_EXEMPT_FINANCIAL",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["CURRENT_ASSETS", "CURRENT_LIABILITIES"],
                    source_periods=[period.period_key],
                    methodology_notes="Unclassified balance sheet; exempt from Altman scoring.",
                ),
            )
            return AltmanZScoreResult(
                dispatched_model="EXEMPT_FINANCIAL",
                dispatch_rationale="Unclassified balance sheet indicates financial or regulated entity.",
                coefficients={},
                factors={},
                total_score=None,
                zone=None,
                metric_result=unavailable_res,
            )

        # 2. Structural Model Dispatch
        dispatched_model: Literal["MODEL_1_MANUFACTURING", "MODEL_2_SERVICE"]
        dispatch_rationale: str

        if altman_model_override is not None:
            norm_override = altman_model_override.strip().upper()
            if norm_override in ("MANUFACTURING", "MODEL_1", "MODEL_1_MANUFACTURING"):
                dispatched_model = "MODEL_1_MANUFACTURING"
                dispatch_rationale = (
                    "User/analyst explicit model override: Model 1 (Manufacturing)."
                )
            else:
                dispatched_model = "MODEL_2_SERVICE"
                dispatch_rationale = (
                    "User/analyst explicit model override: Model 2 (Service Z'')."
                )
        else:
            # AURELIUS V1 Structural Dispatch Heuristics (Inventory >= 5% and PPE >= 15%)
            inv_fact = fact_store.get_canonical_fact(
                StatementType.BALANCE_SHEET,
                CanonicalConcept.INVENTORY,
                period.period_key,
            )
            if inv_fact is None:
                inv_fact = fact_store.get_source_fact(
                    StatementType.BALANCE_SHEET,
                    ["Inventory"],
                    period.period_key,
                )

            ppe_fact = fact_store.get_source_fact(
                StatementType.BALANCE_SHEET,
                [
                    "Net PPE",
                    "Property Plant Equipment Net",
                    "Property Plant And Equipment Net",
                    "Net Property Plant And Equipment",
                ],
                period.period_key,
            )

            if ta_fact is not None and ta_fact.value > Decimal(0):
                inv_intensity = (
                    (inv_fact.value / ta_fact.value) if inv_fact else Decimal(0)
                )
                ppe_intensity = (
                    (ppe_fact.value / ta_fact.value) if ppe_fact else Decimal(0)
                )

                if inv_fact is None and ppe_fact is None:
                    dispatched_model = "MODEL_2_SERVICE"
                    dispatch_rationale = "AURELIUS methodology choice: ambiguous/borderline physical asset disclosures; defaulted to general corporate Z'' model."
                    diagnostics.append(
                        MetricDiagnostic(
                            code=DiagnosticCode.ALTMAN_AMBIGUOUS_STRUCTURE_DISPATCH_SERVICE,
                            message=dispatch_rationale,
                            details={"period": period.period_key},
                        )
                    )
                elif inv_intensity >= Decimal("0.05") and ppe_intensity >= Decimal(
                    "0.15"
                ):
                    dispatched_model = "MODEL_1_MANUFACTURING"
                    dispatch_rationale = f"AURELIUS heuristic dispatch: Inventory intensity ({inv_intensity:.1%}) >= 5% and PPE intensity ({ppe_intensity:.1%}) >= 15% consistent with goods manufacturing."
                    diagnostics.append(
                        MetricDiagnostic(
                            code=DiagnosticCode.ALTMAN_MODEL_DISPATCHED_MANUFACTURING,
                            message=dispatch_rationale,
                            details={
                                "inventory_intensity": str(inv_intensity),
                                "ppe_intensity": str(ppe_intensity),
                                "period": period.period_key,
                            },
                        )
                    )
                else:
                    dispatched_model = "MODEL_2_SERVICE"
                    dispatch_rationale = f"AURELIUS heuristic dispatch: Asset-light operational profile (Inventory {inv_intensity:.1%}, PPE {ppe_intensity:.1%}); 4-variable Z'' model dispatched."
                    diagnostics.append(
                        MetricDiagnostic(
                            code=DiagnosticCode.ALTMAN_MODEL_DISPATCHED_SERVICE,
                            message=dispatch_rationale,
                            details={
                                "inventory_intensity": str(inv_intensity),
                                "ppe_intensity": str(ppe_intensity),
                                "period": period.period_key,
                            },
                        )
                    )
            else:
                dispatched_model = "MODEL_2_SERVICE"
                dispatch_rationale = "AURELIUS fallback: Total Assets unavailable; defaulted to Model 2 (Service)."

        # 3. Factor Construction
        missing_factors: list[str] = []

        if ta_fact is None or ta_fact.value <= Decimal(0):
            missing_factors.append("Total Assets")
        else:
            source_fact_ids.append(ta_fact.fact_id)
            source_concepts.append("TOTAL_ASSETS")

        if ca_fact is None:
            missing_factors.append("Current Assets")
        else:
            source_fact_ids.append(ca_fact.fact_id)
            source_concepts.append("CURRENT_ASSETS")

        if cl_fact is None:
            missing_factors.append("Current Liabilities")
        else:
            source_fact_ids.append(cl_fact.fact_id)
            source_concepts.append("CURRENT_LIABILITIES")

        # Retained Earnings (X2)
        re_fact = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            ["Retained Earnings", "Retained Earnings Total Equity"],
            period.period_key,
        )
        if re_fact is None:
            missing_factors.append("Retained Earnings")
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.MISSING_REQUIRED_FACT,
                    message="Retained Earnings is absent from balance sheet; required for Altman X2 factor.",
                    details={"period": period.period_key},
                )
            )
        else:
            source_fact_ids.append(re_fact.fact_id)
            source_concepts.append("Retained Earnings")

        # Operating Income (X3)
        ebit_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.OPERATING_INCOME,
            period.period_key,
        )
        if ebit_fact is None:
            missing_factors.append("Operating Income")
        else:
            source_fact_ids.append(ebit_fact.fact_id)
            source_concepts.append("OPERATING_INCOME")

        # Total Liabilities (X4 denominator)
        tl_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.TOTAL_LIABILITIES,
            period.period_key,
        )
        tl_val: Decimal | None = None
        if tl_fact is not None and tl_fact.value > Decimal(0):
            tl_val = tl_fact.value
            source_fact_ids.append(tl_fact.fact_id)
            source_concepts.append("TOTAL_LIABILITIES")
        else:
            # Fallback: Total Assets - Stockholders Equity
            eq_fact = fact_store.get_canonical_fact(
                StatementType.BALANCE_SHEET,
                CanonicalConcept.STOCKHOLDERS_EQUITY,
                period.period_key,
            )
            if (
                ta_fact is not None
                and eq_fact is not None
                and (ta_fact.value - eq_fact.value) > Decimal(0)
            ):
                tl_val = ta_fact.value - eq_fact.value
                source_fact_ids.extend([ta_fact.fact_id, eq_fact.fact_id])
                source_concepts.extend(["TOTAL_ASSETS", "STOCKHOLDERS_EQUITY"])
            else:
                missing_factors.append("Total Liabilities")

        # Market Capitalization (X4 numerator)
        if market_cap is None or market_cap <= Decimal(0):
            missing_factors.append("Market Capitalization")
            if market_cap is None:
                diagnostics.append(
                    MetricDiagnostic(
                        code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                        message="Market capitalization is unavailable; required for Altman X4 factor.",
                        details={"period": period.period_key},
                    )
                )
            else:
                diagnostics.append(
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_MARKET_CAP,
                        message="Market capitalization is non-positive.",
                        details={"period": period.period_key},
                    )
                )

        # Revenue (X5 for Model 1 only)
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.REVENUE,
            period.period_key,
        )
        if dispatched_model == "MODEL_1_MANUFACTURING":
            if rev_fact is None:
                missing_factors.append("Revenue")
            else:
                source_fact_ids.append(rev_fact.fact_id)
                source_concepts.append("REVENUE")

        if missing_factors:
            unavailable_res = MetricResult(
                metric_id=FundamentalMetricId.ALTMAN_Z_SCORE,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id=(
                        "FORMULA_ALTMAN_Z_MANUFACTURING_V1"
                        if dispatched_model == "MODEL_1_MANUFACTURING"
                        else "FORMULA_ALTMAN_Z_SERVICE_V1"
                    ),
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=missing_factors,
                    source_periods=[period.period_key],
                    methodology_notes=f"Missing factors for Altman Z-Score: {', '.join(missing_factors)}.",
                ),
            )
            return AltmanZScoreResult(
                dispatched_model=dispatched_model,
                dispatch_rationale=dispatch_rationale,
                coefficients={},
                factors={},
                total_score=None,
                zone=None,
                metric_result=unavailable_res,
            )

        assert ta_fact is not None and ta_fact.value > Decimal(0)
        assert ca_fact is not None
        assert cl_fact is not None
        assert re_fact is not None
        assert ebit_fact is not None
        assert tl_val is not None
        assert market_cap is not None

        # Compute factor values
        x1 = (ca_fact.value - cl_fact.value) / ta_fact.value
        x2 = re_fact.value / ta_fact.value
        x3 = ebit_fact.value / ta_fact.value
        x4 = market_cap / tl_val

        factors: dict[str, Decimal] = {"X1": x1, "X2": x2, "X3": x3, "X4": x4}
        coefficients: dict[str, Decimal]

        if dispatched_model == "MODEL_1_MANUFACTURING":
            assert rev_fact is not None
            x5 = rev_fact.value / ta_fact.value
            factors["X5"] = x5
            coefficients = {
                "X1": Decimal("1.2"),
                "X2": Decimal("1.4"),
                "X3": Decimal("3.3"),
                "X4": Decimal("0.6"),
                "X5": Decimal("0.999"),
            }
            z_score = (
                coefficients["X1"] * x1
                + coefficients["X2"] * x2
                + coefficients["X3"] * x3
                + coefficients["X4"] * x4
                + coefficients["X5"] * x5
            )
            # Zones of Discrimination (Model 1): Safe > 2.99, Grey 1.81..2.99, Distress < 1.81
            if z_score > Decimal("2.99"):
                zone: Literal["SAFE", "GREY", "DISTRESS"] = "SAFE"
            elif z_score >= Decimal("1.81"):
                zone = "GREY"
            else:
                zone = "DISTRESS"

            formula_id = "FORMULA_ALTMAN_Z_MANUFACTURING_V1"
        else:
            coefficients = {
                "X1": Decimal("6.56"),
                "X2": Decimal("3.26"),
                "X3": Decimal("6.72"),
                "X4": Decimal("1.05"),
            }
            z_score = (
                coefficients["X1"] * x1
                + coefficients["X2"] * x2
                + coefficients["X3"] * x3
                + coefficients["X4"] * x4
            )
            # Zones of Discrimination (Model 2): Safe > 2.60, Grey 1.10..2.60, Distress < 1.10
            if z_score > Decimal("2.60"):
                zone = "SAFE"
            elif z_score >= Decimal("1.10"):
                zone = "GREY"
            else:
                zone = "DISTRESS"

            formula_id = "FORMULA_ALTMAN_Z_SERVICE_V1"

        metric_result = MetricResult(
            metric_id=FundamentalMetricId.ALTMAN_Z_SCORE,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=z_score,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id=formula_id,
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=list(dict.fromkeys(source_fact_ids)),
                source_concepts=list(dict.fromkeys(source_concepts)),
                source_periods=[period.period_key],
                methodology_notes=(
                    f"Altman Z-Score ({dispatched_model}) = {z_score} (Zone: {zone}). "
                    f"Dispatch Rationale: {dispatch_rationale}"
                ),
            ),
        )

        return AltmanZScoreResult(
            dispatched_model=dispatched_model,
            dispatch_rationale=dispatch_rationale,
            coefficients=coefficients,
            factors=factors,
            total_score=z_score,
            zone=zone,
            metric_result=metric_result,
        )
