"""
aurelius.domain.fundamental.engines.profitability
=================================================
Pure calculation engine for canonical profitability metrics: Gross Profit,
Gross Margin, Operating Income, Operating Margin, Net Income, Net Margin,
ROA, ROE, and reported EBITDA Margin.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialPeriod,
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
)


class ProfitabilityEngine:
    """
    Engine calculating profitability margins and return metrics.
    """

    @staticmethod
    def resolve_gross_profit(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> tuple[
        Decimal | None,
        bool,
        list[str],
        list[str],
        str,
        str | None,
        MetricDiagnostic | None,
    ]:
        """
        Resolve Gross Profit:
          1. Use reported canonical GROSS_PROFIT if present.
          2. Fallback to derived (REVENUE - COST_OF_REVENUE) if both exist.
          3. Return missing diagnostic if neither is available.

        Returns:
          (value, is_derived, source_fact_ids, source_concepts, formula_id, notes, diagnostic)
        """
        reported_gp = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.GROSS_PROFIT,
            period.period_key,
        )
        if reported_gp is not None:
            return (
                reported_gp.value,
                False,
                [reported_gp.fact_id],
                ["GROSS_PROFIT"],
                "REPORTED_GROSS_PROFIT",
                None,
                None,
            )

        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.REVENUE, period.period_key
        )
        cogs_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.COST_OF_REVENUE,
            period.period_key,
        )

        if rev_fact is not None and cogs_fact is not None:
            derived_gp = rev_fact.value - cogs_fact.value
            return (
                derived_gp,
                True,
                [rev_fact.fact_id, cogs_fact.fact_id],
                ["REVENUE", "COST_OF_REVENUE"],
                "FORMULA_GROSS_PROFIT_FROM_REVENUE_COGS",
                "Gross Profit derived from Revenue minus Cost of Revenue because reported Gross Profit was unavailable.",
                None,
            )

        missing = []
        if rev_fact is None:
            missing.append("REVENUE")
        if cogs_fact is None:
            missing.append("COST_OF_REVENUE")

        diag = MetricDiagnostic(
            code=DiagnosticCode.MISSING_REQUIRED_FACT,
            message="Reported Gross Profit is unavailable and cannot be derived (missing Revenue or Cost of Revenue).",
            details={
                "missing_concepts": ", ".join(missing),
                "period": period.period_key,
            },
        )
        return (None, False, [], [], "FORMULA_GROSS_PROFIT", None, diag)

    @classmethod
    def calculate_gross_profit(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate or retrieve Gross Profit.
        """
        val, is_derived, fact_ids, concepts, formula_id, notes, diag = (
            cls.resolve_gross_profit(period, fact_store)
        )
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.REVENUE, period.period_key
        )
        curr = rev_fact.currency if rev_fact else None

        if val is None or diag is not None:
            return MetricResult(
                metric_id=FundamentalMetricId.GROSS_PROFIT,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=curr,
                period=period,
                diagnostics=[diag] if diag else [],
                provenance=MetricProvenance(
                    formula_id=formula_id,
                    source_concepts=concepts,
                    source_periods=[period.period_key],
                ),
                is_derived=is_derived,
            )

        return MetricResult(
            metric_id=FundamentalMetricId.GROSS_PROFIT,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=val,
            unit=Unit.CURRENCY,
            currency=curr,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id=formula_id,
                source_fact_ids=fact_ids,
                source_concepts=concepts,
                source_periods=[period.period_key],
                methodology_notes=notes,
            ),
            is_derived=is_derived,
        )

    @classmethod
    def calculate_gross_margin(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Gross Profit Margin: Gross Profit / Revenue.
        """
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.REVENUE, period.period_key
        )
        if rev_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.GROSS_PROFIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Revenue fact is missing for Gross Margin calculation.",
                        details={"concept": "REVENUE", "period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_GROSS_PROFIT_MARGIN",
                    source_concepts=["REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        if rev_fact.value <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.GROSS_PROFIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_OR_NEGATIVE_REVENUE,
                        message="Revenue is zero or negative; Gross Margin is economically undefined.",
                        details={"revenue": str(rev_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_GROSS_PROFIT_MARGIN",
                    source_fact_ids=[rev_fact.fact_id],
                    source_concepts=["REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        gp_val, is_derived, fact_ids, concepts, formula_id, notes, diag = (
            cls.resolve_gross_profit(period, fact_store)
        )
        if gp_val is None or diag is not None:
            return MetricResult(
                metric_id=FundamentalMetricId.GROSS_PROFIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[diag] if diag else [],
                provenance=MetricProvenance(
                    formula_id="FORMULA_GROSS_PROFIT_MARGIN",
                    source_fact_ids=[rev_fact.fact_id],
                    source_concepts=["REVENUE", *concepts],
                    source_periods=[period.period_key],
                ),
            )

        margin = gp_val / rev_fact.value
        all_facts = list(dict.fromkeys([rev_fact.fact_id, *fact_ids]))
        all_concepts = list(dict.fromkeys(["REVENUE", *concepts]))

        return MetricResult(
            metric_id=FundamentalMetricId.GROSS_PROFIT_MARGIN,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=margin,
            unit=Unit.PERCENT,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id=(
                    "FORMULA_GROSS_MARGIN_FROM_DERIVED_GP"
                    if is_derived
                    else "FORMULA_GROSS_MARGIN_FROM_REPORTED_GP"
                ),
                source_fact_ids=all_facts,
                source_concepts=all_concepts,
                source_periods=[period.period_key],
                methodology_notes=notes,
            ),
            is_derived=True,
        )

    @staticmethod
    def calculate_operating_income(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve canonical Operating Income (EBIT).
        """
        fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.OPERATING_INCOME,
            period.period_key,
        )
        if fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_INCOME,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Operating Income fact is missing.",
                        details={
                            "concept": "OPERATING_INCOME",
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="REPORTED_OPERATING_INCOME",
                    source_concepts=["OPERATING_INCOME"],
                    source_periods=[period.period_key],
                ),
                is_derived=False,
            )

        return MetricResult(
            metric_id=FundamentalMetricId.OPERATING_INCOME,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=fact.value,
            unit=Unit.CURRENCY,
            currency=fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="REPORTED_OPERATING_INCOME",
                source_fact_ids=[fact.fact_id],
                source_concepts=["OPERATING_INCOME"],
                source_periods=[period.period_key],
            ),
            is_derived=False,
        )

    @staticmethod
    def calculate_operating_margin(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Operating Margin: Operating Income / Revenue.
        Negative EBIT with positive revenue is VALID (valid negative operating margin).
        """
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.REVENUE, period.period_key
        )
        ebit_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.OPERATING_INCOME,
            period.period_key,
        )

        missing = []
        if rev_fact is None:
            missing.append("REVENUE")
        if ebit_fact is None:
            missing.append("OPERATING_INCOME")

        if missing:
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for Operating Margin: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_OPERATING_MARGIN",
                    source_concepts=["OPERATING_INCOME", "REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        if rev_fact.value <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_OR_NEGATIVE_REVENUE,
                        message="Revenue is zero or negative; Operating Margin is undefined.",
                        details={"revenue": str(rev_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_OPERATING_MARGIN",
                    source_fact_ids=[ebit_fact.fact_id, rev_fact.fact_id],
                    source_concepts=["OPERATING_INCOME", "REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        margin = ebit_fact.value / rev_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.OPERATING_MARGIN,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=margin,
            unit=Unit.PERCENT,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_OPERATING_MARGIN",
                source_fact_ids=[ebit_fact.fact_id, rev_fact.fact_id],
                source_concepts=["OPERATING_INCOME", "REVENUE"],
                source_periods=[period.period_key],
            ),
        )

    @staticmethod
    def calculate_net_income(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve canonical Net Income.
        """
        fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.NET_INCOME,
            period.period_key,
        )
        if fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.NET_INCOME,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Net Income fact is missing.",
                        details={"concept": "NET_INCOME", "period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="REPORTED_NET_INCOME",
                    source_concepts=["NET_INCOME"],
                    source_periods=[period.period_key],
                ),
                is_derived=False,
            )

        return MetricResult(
            metric_id=FundamentalMetricId.NET_INCOME,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=fact.value,
            unit=Unit.CURRENCY,
            currency=fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="REPORTED_NET_INCOME",
                source_fact_ids=[fact.fact_id],
                source_concepts=["NET_INCOME"],
                source_periods=[period.period_key],
            ),
            is_derived=False,
        )

    @staticmethod
    def calculate_net_profit_margin(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Net Profit Margin: Net Income / Revenue.
        """
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.REVENUE, period.period_key
        )
        ni_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.NET_INCOME,
            period.period_key,
        )

        missing = []
        if rev_fact is None:
            missing.append("REVENUE")
        if ni_fact is None:
            missing.append("NET_INCOME")

        if missing:
            return MetricResult(
                metric_id=FundamentalMetricId.NET_PROFIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for Net Profit Margin: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_PROFIT_MARGIN",
                    source_concepts=["NET_INCOME", "REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        if rev_fact.value <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.NET_PROFIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_OR_NEGATIVE_REVENUE,
                        message="Revenue is zero or negative; Net Profit Margin is undefined.",
                        details={"revenue": str(rev_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_PROFIT_MARGIN",
                    source_fact_ids=[ni_fact.fact_id, rev_fact.fact_id],
                    source_concepts=["NET_INCOME", "REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        margin = ni_fact.value / rev_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.NET_PROFIT_MARGIN,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=margin,
            unit=Unit.PERCENT,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_NET_PROFIT_MARGIN",
                source_fact_ids=[ni_fact.fact_id, rev_fact.fact_id],
                source_concepts=["NET_INCOME", "REVENUE"],
                source_periods=[period.period_key],
            ),
        )

    @staticmethod
    def calculate_roa(
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Return on Assets (ROA): Net Income / Average Total Assets.
        """
        ni_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.NET_INCOME,
            current_period.period_key,
        )
        if ni_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.RETURN_ON_ASSETS,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Net Income is missing for ROA calculation.",
                        details={
                            "concept": "NET_INCOME",
                            "period": current_period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROA_2PT_AVG",
                    source_concepts=["NET_INCOME", "TOTAL_ASSETS"],
                    source_periods=[current_period.period_key],
                ),
            )

        avg_assets, diag, used_fb, asset_facts = calculate_two_point_average(
            CanonicalConcept.TOTAL_ASSETS,
            current_period,
            prior_period,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_fact_ids = [ni_fact.fact_id, *(f.fact_id for f in asset_facts)]
        all_periods = list(
            dict.fromkeys(
                [current_period.period_key, *(f.period.period_key for f in asset_facts)]
            )
        )

        if avg_assets is None or diag is not None and not used_fb:
            return MetricResult(
                metric_id=FundamentalMetricId.RETURN_ON_ASSETS,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[diag] if diag else [],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROA_2PT_AVG",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["NET_INCOME", "TOTAL_ASSETS"],
                    source_periods=all_periods,
                ),
            )

        if avg_assets <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.RETURN_ON_ASSETS,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Average Total Assets is zero or negative; ROA is undefined.",
                        details={"assets": str(avg_assets)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROA_2PT_AVG",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["NET_INCOME", "TOTAL_ASSETS"],
                    source_periods=all_periods,
                ),
            )

        roa = ni_fact.value / avg_assets
        diagnostics = [diag] if diag and used_fb else []
        notes = (
            "Ending point-in-time assets used under fallback mode."
            if used_fb
            else "Two-point average balance sheet assets used."
        )

        return MetricResult(
            metric_id=FundamentalMetricId.RETURN_ON_ASSETS,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=roa,
            unit=Unit.PERCENT,
            currency=None,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_ROA_POINT_IN_TIME"
                if used_fb
                else "FORMULA_ROA_2PT_AVG",
                source_fact_ids=all_fact_ids,
                source_concepts=["NET_INCOME", "TOTAL_ASSETS"],
                source_periods=all_periods,
                methodology_notes=notes,
            ),
        )

    @staticmethod
    def calculate_roe(
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Return on Equity (ROE): Net Income / Average Stockholders' Equity.
        Average Equity <= 0 returns DISTORTED with NEGATIVE_OR_ZERO_EQUITY.
        """
        ni_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.NET_INCOME,
            current_period.period_key,
        )
        if ni_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.RETURN_ON_EQUITY,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Net Income is missing for ROE calculation.",
                        details={
                            "concept": "NET_INCOME",
                            "period": current_period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROE_2PT_AVG",
                    source_concepts=["NET_INCOME", "STOCKHOLDERS_EQUITY"],
                    source_periods=[current_period.period_key],
                ),
            )

        avg_equity, diag, used_fb, equity_facts = calculate_two_point_average(
            CanonicalConcept.STOCKHOLDERS_EQUITY,
            current_period,
            prior_period,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_fact_ids = [ni_fact.fact_id, *(f.fact_id for f in equity_facts)]
        all_periods = list(
            dict.fromkeys(
                [
                    current_period.period_key,
                    *(f.period.period_key for f in equity_facts),
                ]
            )
        )

        if avg_equity is None or diag is not None and not used_fb:
            return MetricResult(
                metric_id=FundamentalMetricId.RETURN_ON_EQUITY,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[diag] if diag else [],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROE_2PT_AVG",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["NET_INCOME", "STOCKHOLDERS_EQUITY"],
                    source_periods=all_periods,
                ),
            )

        if avg_equity <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.RETURN_ON_EQUITY,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NEGATIVE_OR_ZERO_EQUITY,
                        message="Average Stockholders' Equity is zero or negative; ROE is distorted/undefined.",
                        details={"equity": str(avg_equity)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ROE_2PT_AVG",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["NET_INCOME", "STOCKHOLDERS_EQUITY"],
                    source_periods=all_periods,
                ),
            )

        roe = ni_fact.value / avg_equity
        diagnostics = [diag] if diag and used_fb else []
        notes = (
            "Ending point-in-time equity used under fallback mode."
            if used_fb
            else "Two-point average equity used."
        )

        return MetricResult(
            metric_id=FundamentalMetricId.RETURN_ON_EQUITY,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=roe,
            unit=Unit.PERCENT,
            currency=None,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_ROE_POINT_IN_TIME"
                if used_fb
                else "FORMULA_ROE_2PT_AVG",
                source_fact_ids=all_fact_ids,
                source_concepts=["NET_INCOME", "STOCKHOLDERS_EQUITY"],
                source_periods=all_periods,
                methodology_notes=notes,
            ),
        )

    @staticmethod
    def calculate_ebitda_margin(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate EBITDA Margin: Reported EBITDA / Revenue.
        Strictly requires provider-reported EBITDA. Never synthesized in M7A.
        """
        ebitda_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.EBITDA, period.period_key
        )
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.REVENUE, period.period_key
        )

        if ebitda_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.EBITDA_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_REPORTED_EBITDA_RESTRICTION,
                        message="EBITDA is not reported directly by the provider. Synthetic EBITDA is prohibited.",
                        details={"concept": "EBITDA", "period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EBITDA_MARGIN_REPORTED",
                    source_concepts=["EBITDA", "REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        if rev_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.EBITDA_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Revenue fact is missing for EBITDA Margin calculation.",
                        details={"concept": "REVENUE", "period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EBITDA_MARGIN_REPORTED",
                    source_fact_ids=[ebitda_fact.fact_id],
                    source_concepts=["EBITDA", "REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        if rev_fact.value <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.EBITDA_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_OR_NEGATIVE_REVENUE,
                        message="Revenue is zero or negative; EBITDA Margin is undefined.",
                        details={"revenue": str(rev_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_EBITDA_MARGIN_REPORTED",
                    source_fact_ids=[ebitda_fact.fact_id, rev_fact.fact_id],
                    source_concepts=["EBITDA", "REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        margin = ebitda_fact.value / rev_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.EBITDA_MARGIN,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=margin,
            unit=Unit.PERCENT,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_EBITDA_MARGIN_REPORTED",
                source_fact_ids=[ebitda_fact.fact_id, rev_fact.fact_id],
                source_concepts=["EBITDA", "REVENUE"],
                source_periods=[period.period_key],
                methodology_notes="Computed strictly from source-reported EBITDA.",
            ),
        )
