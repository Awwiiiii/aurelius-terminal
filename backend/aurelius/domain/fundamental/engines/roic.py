"""
aurelius.domain.fundamental.engines.roic
========================================
Pure calculation engine for Return on Invested Capital (ROIC),
Net Operating Profit After Taxes (NOPAT), Effective Tax Rate (ETR),
and Invested Capital (IC).

Key Invariants:
  - ETR = Income Tax Expense / EBT (Pretax Income).
  - AURELIUS V1 Methodology Boundary:
      * EBT <= 0 -> ETR unavailable.
      * Income Tax Expense <= 0 with EBT > 0 -> ETR unavailable.
      * ETR >= 1.0 -> ETR unavailable.
      * Missing tax inputs -> ETR unavailable.
      * Diagnostic: UNAVAILABLE_EFFECTIVE_TAX_RATE.
      * No statutory tax fallback, no hard-coded rate, no smoothed fallback.
  - NOPAT = EBIT * (1 - ETR).
      * Negative EBIT with valid ETR -> calculated with NEGATIVE_OPERATING_PROFIT diagnostic.
  - Invested Capital = Gross Debt + Stockholders' Equity - Cash and Equivalents.
      * Preserves M7A Gross Debt hierarchy.
  - Average Invested Capital = (IC_beginning + IC_ending) / 2.
      * If beginning IC is missing and allow_point_in_time_fallback=True -> uses IC_ending
        with POINT_IN_TIME_DENOMINATOR_FALLBACK diagnostic.
      * If fallback is False and beginning IC is missing -> UNAVAILABLE.
  - If Average Invested Capital <= 0:
      * ROIC is UNAVAILABLE with NON_POSITIVE_INVESTED_CAPITAL.
      * Denominators are NEVER transformed using abs().
  - ROIC = NOPAT / Average Invested Capital.
  - Full auditable provenance on every derived result.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialFact,
    FinancialPeriod,
    StatementType,
    Unit,
)
from aurelius.domain.fundamental.engines.solvency import SolvencyEngine
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
)
from aurelius.domain.fundamental.ttm import TTMEngine, TTMWindow


class ROICEngine:
    """
    Engine calculating ETR, NOPAT, Invested Capital, and ROIC.
    """

    METHODOLOGY_VERSION = "1.0.0"

    @classmethod
    def calculate_effective_tax_rate(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Effective Tax Rate (ETR): Income Tax Expense / Pretax Income (EBT).

        AURELIUS V1 Methodology Boundary:
          - EBT <= 0 -> UNAVAILABLE
          - Tax Expense <= 0 with EBT > 0 -> UNAVAILABLE
          - ETR >= 1.0 -> UNAVAILABLE
          - Missing inputs -> UNAVAILABLE
          - Diagnostic code: UNAVAILABLE_EFFECTIVE_TAX_RATE
        """
        tax_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.INCOME_TAX_EXPENSE,
            period.period_key,
        )
        ebt_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.PRETAX_INCOME,
            period.period_key,
        )

        all_fact_ids: list[str] = []
        all_concepts: list[str] = ["INCOME_TAX_EXPENSE", "PRETAX_INCOME"]
        all_periods: list[str] = [period.period_key]

        if tax_fact is not None:
            all_fact_ids.append(tax_fact.fact_id)
        if ebt_fact is not None:
            all_fact_ids.append(ebt_fact.fact_id)

        if tax_fact is None or ebt_fact is None:
            missing = []
            if tax_fact is None:
                missing.append("INCOME_TAX_EXPENSE")
            if ebt_fact is None:
                missing.append("PRETAX_INCOME")
            return MetricResult(
                metric_id=FundamentalMetricId.EFFECTIVE_TAX_RATE,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE,
                        message=f"Missing required line item(s) for Effective Tax Rate: {', '.join(missing)}.",
                        details={
                            "missing_concepts": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EFFECTIVE_TAX_RATE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="ETR calculation requires both Income Tax Expense and Pretax Income.",
                ),
            )

        tax_val = tax_fact.value
        ebt_val = ebt_fact.value

        # Boundary 1: EBT <= 0
        if ebt_val <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.EFFECTIVE_TAX_RATE,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE,
                        message="Pretax income (EBT) is zero or negative; Effective Tax Rate is outside AURELIUS V1 methodology boundary.",
                        details={"ebt": str(ebt_val), "period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EFFECTIVE_TAX_RATE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="AURELIUS V1 boundary: EBT <= 0 renders operational ETR uninterpretable for NOPAT.",
                ),
            )

        # Boundary 2: Tax Expense <= 0 when EBT > 0
        if tax_val <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.EFFECTIVE_TAX_RATE,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE,
                        message="Income Tax Expense is zero or negative; Effective Tax Rate is outside AURELIUS V1 methodology boundary.",
                        details={
                            "income_tax": str(tax_val),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EFFECTIVE_TAX_RATE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="AURELIUS V1 boundary: Tax Expense <= 0 (benefits/zero tax) renders operational ETR unavailable for NOPAT.",
                ),
            )

        etr = tax_val / ebt_val

        # Boundary 3: ETR >= 1.0
        if etr >= Decimal("1.0"):
            return MetricResult(
                metric_id=FundamentalMetricId.EFFECTIVE_TAX_RATE,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE,
                        message="Effective Tax Rate equals or exceeds 100%; outside AURELIUS V1 methodology boundary.",
                        details={"etr": str(etr), "period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EFFECTIVE_TAX_RATE",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="AURELIUS V1 boundary: ETR >= 100% renders operational ETR uninterpretable for NOPAT.",
                ),
            )

        return MetricResult(
            metric_id=FundamentalMetricId.EFFECTIVE_TAX_RATE,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=etr,
            unit=Unit.PERCENT,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_EFFECTIVE_TAX_RATE",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_fact_ids,
                source_concepts=all_concepts,
                source_periods=all_periods,
                methodology_notes="ETR = Income Tax Expense / Pretax Income (EBT).",
            ),
        )

    @classmethod
    def calculate_nopat(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Net Operating Profit After Taxes (NOPAT): EBIT * (1 - ETR).

        - EBIT is canonical OPERATING_INCOME.
        - ETR must be VALID from calculate_effective_tax_rate.
        - If EBIT < 0 and ETR is valid -> NOPAT is computed with NEGATIVE_OPERATING_PROFIT diagnostic.
        - If ETR is UNAVAILABLE -> NOPAT is UNAVAILABLE with UNAVAILABLE_EFFECTIVE_TAX_RATE.
        - If EBIT is missing -> NOPAT is UNAVAILABLE with MISSING_REQUIRED_FACT.
        """
        ebit_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.OPERATING_INCOME,
            period.period_key,
        )

        etr_result = cls.calculate_effective_tax_rate(period, fact_store)

        all_fact_ids: list[str] = list(etr_result.provenance.source_fact_ids)
        all_concepts: list[str] = list(
            dict.fromkeys(["OPERATING_INCOME", *etr_result.provenance.source_concepts])
        )
        all_periods: list[str] = list(
            dict.fromkeys([period.period_key, *etr_result.provenance.source_periods])
        )

        if ebit_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.NOPAT,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Operating Income (EBIT) is missing for NOPAT calculation.",
                        details={
                            "concept": "OPERATING_INCOME",
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NOPAT",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                ),
            )

        all_fact_ids.insert(0, ebit_fact.fact_id)

        if etr_result.status != MetricStatus.VALID or etr_result.value is None:
            return MetricResult(
                metric_id=FundamentalMetricId.NOPAT,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=ebit_fact.currency,
                period=period,
                diagnostics=list(etr_result.diagnostics),
                provenance=MetricProvenance(
                    formula_id="FORMULA_NOPAT",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="NOPAT unavailable because a valid Effective Tax Rate could not be established under AURELIUS V1 methodology.",
                ),
            )

        etr = etr_result.value
        ebit = ebit_fact.value
        nopat = ebit * (Decimal("1") - etr)

        diagnostics: list[MetricDiagnostic] = []
        notes = "NOPAT = EBIT * (1 - ETR)."
        if ebit < Decimal("0"):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.NEGATIVE_OPERATING_PROFIT,
                    message="Operating Income (EBIT) is negative; NOPAT reflects after-tax operating loss.",
                    details={"ebit": str(ebit), "nopat": str(nopat)},
                )
            )
            notes += " Operating loss detected."

        return MetricResult(
            metric_id=FundamentalMetricId.NOPAT,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=nopat,
            unit=Unit.CURRENCY,
            currency=ebit_fact.currency,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_NOPAT",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_fact_ids,
                source_concepts=all_concepts,
                source_periods=all_periods,
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_invested_capital_point_in_time(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> tuple[
        Decimal | None, list[str], list[str], list[MetricDiagnostic], str | None
    ]:
        """
        Calculate Invested Capital at a single point in time:
        IC = Gross Debt + Stockholders' Equity - Cash and Equivalents.

        Preserves M7A Gross Debt resolution hierarchy via SolvencyEngine.
        Returns:
          (value, fact_ids, concepts, diagnostics, notes)
        """
        gross_debt_val, debt_facts, debt_formula, debt_notes, debt_diag = (
            SolvencyEngine.resolve_gross_debt(period, fact_store)
        )

        equity_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.STOCKHOLDERS_EQUITY,
            period.period_key,
        )

        cash_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
            period.period_key,
        )

        fact_ids: list[str] = [f.fact_id for f in debt_facts]
        concepts: list[str] = ["GROSS_DEBT"]
        diagnostics: list[MetricDiagnostic] = []

        if debt_diag is not None:
            diagnostics.append(debt_diag)

        if equity_fact is not None:
            fact_ids.append(equity_fact.fact_id)
            concepts.append("STOCKHOLDERS_EQUITY")

        if cash_fact is not None:
            fact_ids.append(cash_fact.fact_id)
            concepts.append("CASH_AND_EQUIVALENTS")

        # Missing checks
        missing = []
        if gross_debt_val is None:
            missing.append("GROSS_DEBT")
        if equity_fact is None:
            missing.append("STOCKHOLDERS_EQUITY")
        if cash_fact is None:
            missing.append("CASH_AND_EQUIVALENTS")

        if missing:
            diag = MetricDiagnostic(
                code=DiagnosticCode.MISSING_REQUIRED_FACT,
                message=f"Missing line item(s) for Invested Capital: {', '.join(missing)}.",
                details={
                    "missing_concepts": ", ".join(missing),
                    "period": period.period_key,
                },
            )
            return None, fact_ids, concepts, [diag, *diagnostics], None

        ic_val = gross_debt_val + equity_fact.value - cash_fact.value
        notes = f"Invested Capital = Gross Debt ({gross_debt_val}) + Equity ({equity_fact.value}) - Cash ({cash_fact.value})."
        if debt_notes:
            notes += f" {debt_notes}"

        return ic_val, fact_ids, concepts, diagnostics, notes

    @classmethod
    def calculate_invested_capital(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Invested Capital for a given point-in-time period.
        """
        ic_val, fact_ids, concepts, diagnostics, notes = (
            cls.calculate_invested_capital_point_in_time(period, fact_store)
        )

        if ic_val is None:
            return MetricResult(
                metric_id=FundamentalMetricId.INVESTED_CAPITAL,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_INVESTED_CAPITAL",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=fact_ids,
                    source_concepts=concepts,
                    source_periods=[period.period_key],
                ),
            )

        equity_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.STOCKHOLDERS_EQUITY,
            period.period_key,
        )
        resolved_curr = (
            equity_fact.currency
            if equity_fact and equity_fact.currency
            else getattr(fact_store, "reporting_currency", None)
        )

        return MetricResult(
            metric_id=FundamentalMetricId.INVESTED_CAPITAL,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=ic_val,
            unit=Unit.CURRENCY,
            currency=resolved_curr,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_INVESTED_CAPITAL",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=fact_ids,
                source_concepts=concepts,
                source_periods=[period.period_key],
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_average_invested_capital(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> tuple[
        Decimal | None,
        list[str],
        list[str],
        list[str],
        list[MetricDiagnostic],
        bool,
        str,
    ]:
        """
        Calculate two-point average Invested Capital: (IC_beg + IC_end) / 2.

        Returns:
          (avg_ic, fact_ids, concepts, periods, diagnostics, used_fallback, notes)
        """
        end_ic, end_facts, end_concepts, end_diags, end_notes = (
            cls.calculate_invested_capital_point_in_time(current_period, fact_store)
        )

        all_fact_ids: list[str] = list(end_facts)
        all_concepts: list[str] = list(end_concepts)
        all_periods: list[str] = [current_period.period_key]
        all_diags: list[MetricDiagnostic] = list(end_diags)

        if end_ic is None:
            return (
                None,
                all_fact_ids,
                all_concepts,
                all_periods,
                all_diags,
                False,
                "Ending Invested Capital unavailable.",
            )

        if prior_period is None:
            if allow_point_in_time_fallback:
                fb_diag = MetricDiagnostic(
                    code=DiagnosticCode.POINT_IN_TIME_DENOMINATOR_FALLBACK,
                    message="Prior period Invested Capital is missing; ending point-in-time Invested Capital used under explicit fallback policy.",
                    details={"period": current_period.period_key},
                )
                all_diags.append(fb_diag)
                return (
                    end_ic,
                    all_fact_ids,
                    all_concepts,
                    all_periods,
                    all_diags,
                    True,
                    "Ending point-in-time fallback used for Invested Capital.",
                )
            else:
                missing_diag = MetricDiagnostic(
                    code=DiagnosticCode.MISSING_PRIOR_PERIOD,
                    message="Prior period balance sheet is missing for average Invested Capital.",
                    details={"current_period": current_period.period_key},
                )
                all_diags.append(missing_diag)
                return (
                    None,
                    all_fact_ids,
                    all_concepts,
                    all_periods,
                    all_diags,
                    False,
                    "Prior period missing; fallback disabled.",
                )

        beg_ic, beg_facts, beg_concepts, beg_diags, beg_notes = (
            cls.calculate_invested_capital_point_in_time(prior_period, fact_store)
        )

        all_fact_ids.extend(beg_facts)
        all_concepts = list(dict.fromkeys([*all_concepts, *beg_concepts]))
        all_periods.append(prior_period.period_key)

        if beg_ic is None:
            if allow_point_in_time_fallback:
                fb_diag = MetricDiagnostic(
                    code=DiagnosticCode.POINT_IN_TIME_DENOMINATOR_FALLBACK,
                    message="Prior period Invested Capital computation failed; ending point-in-time Invested Capital used under explicit fallback policy.",
                    details={"period": current_period.period_key},
                )
                all_diags.extend(beg_diags)
                all_diags.append(fb_diag)
                return (
                    end_ic,
                    all_fact_ids,
                    all_concepts,
                    all_periods,
                    all_diags,
                    True,
                    "Ending point-in-time fallback used because prior period IC was unavailable.",
                )
            else:
                all_diags.extend(beg_diags)
                return (
                    None,
                    all_fact_ids,
                    all_concepts,
                    all_periods,
                    all_diags,
                    False,
                    "Prior period IC unavailable; fallback disabled.",
                )

        avg_ic = (beg_ic + end_ic) / Decimal("2")
        notes = f"Average Invested Capital = (Beginning IC ({beg_ic}) + Ending IC ({end_ic})) / 2."
        return avg_ic, all_fact_ids, all_concepts, all_periods, all_diags, False, notes

    @classmethod
    def calculate_roic(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Return on Invested Capital (ROIC): NOPAT / Average Invested Capital.

        Rules:
          - NOPAT must be valid from calculate_nopat.
          - Average IC must be strictly > 0.
          - If Average IC <= 0 -> UNAVAILABLE with NON_POSITIVE_INVESTED_CAPITAL.
          - Denominator is NEVER transformed using abs().
        """
        nopat_result = cls.calculate_nopat(current_period, fact_store)

        avg_ic, ic_facts, ic_concepts, ic_periods, ic_diags, used_fb, ic_notes = (
            cls.calculate_average_invested_capital(
                current_period, prior_period, fact_store, allow_point_in_time_fallback
            )
        )

        all_fact_ids: list[str] = list(
            dict.fromkeys([*nopat_result.provenance.source_fact_ids, *ic_facts])
        )
        all_concepts: list[str] = list(
            dict.fromkeys([*nopat_result.provenance.source_concepts, *ic_concepts])
        )
        all_periods: list[str] = list(
            dict.fromkeys([*nopat_result.provenance.source_periods, *ic_periods])
        )
        all_diags: list[MetricDiagnostic] = list(nopat_result.diagnostics) + list(
            ic_diags
        )

        # Check NOPAT validity
        if nopat_result.status != MetricStatus.VALID or nopat_result.value is None:
            return MetricResult(
                metric_id=FundamentalMetricId.ROIC,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=all_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROIC",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="ROIC unavailable due to uncomputable NOPAT.",
                ),
            )

        # Check Invested Capital validity
        if avg_ic is None:
            return MetricResult(
                metric_id=FundamentalMetricId.ROIC,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=all_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROIC",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes=ic_notes,
                ),
            )

        # Denominator rule: Average IC <= 0
        if avg_ic <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.ROIC,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_INVESTED_CAPITAL,
                        message="Average Invested Capital is zero or negative; ROIC is economically uncomputable.",
                        details={
                            "average_invested_capital": str(avg_ic),
                            "period": current_period.period_key,
                        },
                    ),
                    *all_diags,
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROIC",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="ROIC unavailable: Average Invested Capital is <= 0. Denominators are not converted via abs().",
                ),
            )

        roic = nopat_result.value / avg_ic
        formula_id = "FORMULA_ROIC_POINT_IN_TIME" if used_fb else "FORMULA_ROIC_2PT_AVG"
        notes = f"ROIC = NOPAT ({nopat_result.value}) / Average Invested Capital ({avg_ic}). {ic_notes}"

        return MetricResult(
            metric_id=FundamentalMetricId.ROIC,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=roic,
            unit=Unit.PERCENT,
            currency=None,
            period=current_period,
            diagnostics=all_diags,
            provenance=MetricProvenance(
                formula_id=formula_id,
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_fact_ids,
                source_concepts=all_concepts,
                source_periods=all_periods,
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_ttm_effective_tax_rate(
        cls,
        window: TTMWindow,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Effective Tax Rate across a 4-quarter TTM window:
          ETR = TTM Income Tax Expense / TTM Pretax Income.
        """
        tax_facts: list[FinancialFact] = []
        ebt_facts: list[FinancialFact] = []
        missing_tax_quarters: list[str] = []
        missing_ebt_quarters: list[str] = []

        for q in window.quarters:
            tf = fact_store.get_canonical_fact(
                StatementType.INCOME_STATEMENT,
                CanonicalConcept.INCOME_TAX_EXPENSE,
                q.period_key,
            )
            if tf is not None:
                tax_facts.append(tf)
            else:
                missing_tax_quarters.append(q.period_key)

            ef = fact_store.get_canonical_fact(
                StatementType.INCOME_STATEMENT,
                CanonicalConcept.PRETAX_INCOME,
                q.period_key,
            )
            if ef is not None:
                ebt_facts.append(ef)
            else:
                missing_ebt_quarters.append(q.period_key)

        all_fact_ids = [f.fact_id for f in tax_facts + ebt_facts]
        all_concepts = ["INCOME_TAX_EXPENSE", "PRETAX_INCOME"]
        all_periods = [q.period_key for q in window.quarters]

        if missing_tax_quarters or missing_ebt_quarters:
            return MetricResult(
                metric_id=FundamentalMetricId.EFFECTIVE_TAX_RATE,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE,
                        message=(
                            "TTM Effective Tax Rate unavailable due to missing quarterly facts: "
                            f"tax={missing_tax_quarters}, pretax_income={missing_ebt_quarters}."
                        ),
                        details={
                            "missing_tax": ", ".join(missing_tax_quarters),
                            "missing_ebt": ", ".join(missing_ebt_quarters),
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ETR_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="TTM ETR requires 4 complete quarters of tax and pretax income.",
                ),
            )

        ttm_tax = sum((f.value for f in tax_facts), start=Decimal("0"))
        ttm_ebt = sum((f.value for f in ebt_facts), start=Decimal("0"))

        if ttm_ebt <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.EFFECTIVE_TAX_RATE,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE,
                        message="TTM Pretax Income (EBT) is zero or negative; ETR is economically uncomputable.",
                        details={"ttm_ebt": str(ttm_ebt)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ETR_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                ),
            )

        if ttm_tax <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.EFFECTIVE_TAX_RATE,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE,
                        message="TTM Income Tax Expense is zero or negative with positive EBT; ETR is uncomputable.",
                        details={"ttm_tax": str(ttm_tax), "ttm_ebt": str(ttm_ebt)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ETR_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                ),
            )

        etr_val = ttm_tax / ttm_ebt
        if etr_val >= Decimal("1.0"):
            return MetricResult(
                metric_id=FundamentalMetricId.EFFECTIVE_TAX_RATE,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.UNAVAILABLE_EFFECTIVE_TAX_RATE,
                        message="TTM Effective Tax Rate >= 100%; economically non-standard and rejected.",
                        details={"ttm_etr": str(etr_val)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ETR_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_fact_ids,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                ),
            )

        return MetricResult(
            metric_id=FundamentalMetricId.EFFECTIVE_TAX_RATE,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=etr_val,
            unit=Unit.PERCENT,
            currency=None,
            period=window.ttm_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_ETR_TTM",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_fact_ids,
                source_concepts=all_concepts,
                source_periods=all_periods,
                methodology_notes=f"TTM ETR = TTM Tax ({ttm_tax}) / TTM EBT ({ttm_ebt}).",
            ),
        )

    @classmethod
    def calculate_ttm_nopat(
        cls,
        window: TTMWindow,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate TTM NOPAT: TTM Operating Income (EBIT) * (1 - TTM ETR).
        """
        ebit_res = TTMEngine.calculate_ttm_operating_income(window, fact_store)
        etr_res = cls.calculate_ttm_effective_tax_rate(window, fact_store)

        all_facts = list(
            dict.fromkeys(
                [
                    *ebit_res.provenance.source_fact_ids,
                    *etr_res.provenance.source_fact_ids,
                ]
            )
        )
        all_concepts = list(
            dict.fromkeys(
                [
                    *ebit_res.provenance.source_concepts,
                    *etr_res.provenance.source_concepts,
                ]
            )
        )
        all_periods = list(
            dict.fromkeys(
                [
                    *ebit_res.provenance.source_periods,
                    *etr_res.provenance.source_periods,
                ]
            )
        )
        all_diags = list(ebit_res.diagnostics) + list(etr_res.diagnostics)

        if (
            ebit_res.status != MetricStatus.VALID
            or ebit_res.value is None
            or etr_res.status != MetricStatus.VALID
            or etr_res.value is None
        ):
            return MetricResult(
                metric_id=FundamentalMetricId.NOPAT,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=ebit_res.currency,
                period=window.ttm_period,
                diagnostics=all_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_NOPAT_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_facts,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="TTM NOPAT requires valid TTM EBIT and valid TTM ETR.",
                ),
            )

        diags = list(all_diags)
        if ebit_res.value < Decimal("0"):
            diags.append(
                MetricDiagnostic(
                    code=DiagnosticCode.NEGATIVE_OPERATING_PROFIT,
                    message="TTM Operating Income is negative; NOPAT reflects after-tax operating loss.",
                    details={"ttm_ebit": str(ebit_res.value)},
                )
            )

        nopat_val = ebit_res.value * (Decimal("1") - etr_res.value)
        return MetricResult(
            metric_id=FundamentalMetricId.NOPAT,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=nopat_val,
            unit=Unit.CURRENCY,
            currency=ebit_res.currency,
            period=window.ttm_period,
            diagnostics=diags,
            provenance=MetricProvenance(
                formula_id="FORMULA_NOPAT_TTM",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_facts,
                source_concepts=all_concepts,
                source_periods=all_periods,
                methodology_notes=f"TTM NOPAT = TTM EBIT ({ebit_res.value}) * (1 - TTM ETR ({etr_res.value})).",
            ),
        )

    @classmethod
    def calculate_ttm_roic(
        cls,
        window: TTMWindow,
        prior_anchor: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate TTM ROIC: TTM NOPAT / Average Invested Capital (Q(t-4) to Q(t)).
        """
        nopat_res = cls.calculate_ttm_nopat(window, fact_store)
        avg_ic, ic_facts, ic_concepts, ic_periods, ic_diags, used_fb, ic_notes = (
            cls.calculate_average_invested_capital(
                current_period=window.anchor_quarter,
                prior_period=prior_anchor,
                fact_store=fact_store,
                allow_point_in_time_fallback=allow_point_in_time_fallback,
            )
        )

        all_facts = list(
            dict.fromkeys([*nopat_res.provenance.source_fact_ids, *ic_facts])
        )
        all_concepts = list(
            dict.fromkeys([*nopat_res.provenance.source_concepts, *ic_concepts])
        )
        all_periods = list(
            dict.fromkeys([*nopat_res.provenance.source_periods, *ic_periods])
        )
        all_diags = list(nopat_res.diagnostics) + list(ic_diags)

        if (
            nopat_res.status != MetricStatus.VALID
            or nopat_res.value is None
            or avg_ic is None
        ):
            return MetricResult(
                metric_id=FundamentalMetricId.ROIC,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=all_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROIC_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_facts,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="TTM ROIC unavailable: "
                    + (ic_notes if avg_ic is None else "NOPAT unavailable."),
                ),
            )

        if avg_ic <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.ROIC,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=window.ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_POSITIVE_INVESTED_CAPITAL,
                        message="Average Invested Capital is zero or negative; TTM ROIC is unavailable.",
                        details={"average_invested_capital": str(avg_ic)},
                    ),
                    *all_diags,
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROIC_TTM",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=all_facts,
                    source_concepts=all_concepts,
                    source_periods=all_periods,
                    methodology_notes="Average Invested Capital is <= 0.",
                ),
            )

        roic_val = nopat_res.value / avg_ic
        formula_id = (
            "FORMULA_ROIC_TTM_POINT_IN_TIME" if used_fb else "FORMULA_ROIC_TTM_2PT_AVG"
        )
        return MetricResult(
            metric_id=FundamentalMetricId.ROIC,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=roic_val,
            unit=Unit.PERCENT,
            currency=None,
            period=window.ttm_period,
            diagnostics=all_diags,
            provenance=MetricProvenance(
                formula_id=formula_id,
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_facts,
                source_concepts=all_concepts,
                source_periods=all_periods,
                methodology_notes=f"TTM ROIC = TTM NOPAT ({nopat_res.value}) / Average Invested Capital ({avg_ic}). {ic_notes}",
            ),
        )
