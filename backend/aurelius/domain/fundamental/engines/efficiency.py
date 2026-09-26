"""
aurelius.domain.fundamental.engines.efficiency
==============================================
Pure calculation engine for operating efficiency and working capital velocity:
Asset Turnover, Receivables Turnover, Inventory Turnover, Payables Turnover,
DSO, DIO, DPO, and Cash Conversion Cycle (CCC).
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


class EfficiencyEngine:
    """
    Engine calculating operating turnovers and working capital duration cycles.
    """

    @classmethod
    def calculate_asset_turnover(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Asset Turnover: Revenue / Average Total Assets.
        """
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.REVENUE,
            current_period.period_key,
        )
        if rev_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Revenue fact is missing for Asset Turnover.",
                        details={
                            "concept": "REVENUE",
                            "period": current_period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER",
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
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

        all_fact_ids = [rev_fact.fact_id, *(f.fact_id for f in asset_facts)]
        all_periods = list(
            dict.fromkeys(
                [current_period.period_key, *(f.period.period_key for f in asset_facts)]
            )
        )

        if avg_assets is None or diag is not None and not used_fb:
            return MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[diag] if diag else [],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
                    source_periods=all_periods,
                ),
            )

        if avg_assets <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.ASSET_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Average Total Assets is zero or negative; Asset Turnover is undefined.",
                        details={"assets": str(avg_assets)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_ASSET_TURNOVER",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["REVENUE", "TOTAL_ASSETS"],
                    source_periods=all_periods,
                ),
            )

        turnover = rev_fact.value / avg_assets
        diagnostics = [diag] if diag and used_fb else []
        notes = (
            "Ending point-in-time assets used under fallback mode."
            if used_fb
            else "Two-point average balance sheet assets used."
        )

        return MetricResult(
            metric_id=FundamentalMetricId.ASSET_TURNOVER,
            category=MetricCategory.EFFICIENCY,
            status=MetricStatus.VALID,
            value=turnover,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_ASSET_TURNOVER",
                source_fact_ids=all_fact_ids,
                source_concepts=["REVENUE", "TOTAL_ASSETS"],
                source_periods=all_periods,
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_receivables_turnover(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Receivables Turnover: Revenue / Average Accounts Receivable.
        """
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.REVENUE,
            current_period.period_key,
        )
        if rev_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.RECEIVABLES_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Revenue fact is missing for Receivables Turnover.",
                        details={
                            "concept": "REVENUE",
                            "period": current_period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_RECEIVABLES_TURNOVER",
                    source_concepts=["REVENUE", "ACCOUNTS_RECEIVABLE"],
                    source_periods=[current_period.period_key],
                ),
            )

        avg_ar, diag, used_fb, ar_facts = calculate_two_point_average(
            CanonicalConcept.ACCOUNTS_RECEIVABLE,
            current_period,
            prior_period,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_fact_ids = [rev_fact.fact_id, *(f.fact_id for f in ar_facts)]
        all_periods = list(
            dict.fromkeys(
                [current_period.period_key, *(f.period.period_key for f in ar_facts)]
            )
        )

        if avg_ar is None or diag is not None and not used_fb:
            return MetricResult(
                metric_id=FundamentalMetricId.RECEIVABLES_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[diag] if diag else [],
                provenance=MetricProvenance(
                    formula_id="FORMULA_RECEIVABLES_TURNOVER",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["REVENUE", "ACCOUNTS_RECEIVABLE"],
                    source_periods=all_periods,
                ),
            )

        if avg_ar <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.RECEIVABLES_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Average Accounts Receivable is zero or negative; turnover is undefined.",
                        details={"ar": str(avg_ar)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_RECEIVABLES_TURNOVER",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["REVENUE", "ACCOUNTS_RECEIVABLE"],
                    source_periods=all_periods,
                ),
            )

        turnover = rev_fact.value / avg_ar
        diagnostics = [diag] if diag and used_fb else []
        notes = (
            "Ending point-in-time AR used under fallback mode."
            if used_fb
            else "Two-point average AR used."
        )

        return MetricResult(
            metric_id=FundamentalMetricId.RECEIVABLES_TURNOVER,
            category=MetricCategory.EFFICIENCY,
            status=MetricStatus.VALID,
            value=turnover,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_RECEIVABLES_TURNOVER",
                source_fact_ids=all_fact_ids,
                source_concepts=["REVENUE", "ACCOUNTS_RECEIVABLE"],
                source_periods=all_periods,
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_inventory_turnover(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Inventory Turnover: Cost of Revenue / Average Inventory.
        Strict rule: Uses Cost of Revenue, NEVER Gross Revenue.
        """
        cogs_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.COST_OF_REVENUE,
            current_period.period_key,
        )
        if cogs_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.INVENTORY_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Cost of Revenue fact is missing; entity may be a service company or bank.",
                        details={
                            "concept": "COST_OF_REVENUE",
                            "period": current_period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INVENTORY_TURNOVER_COGS",
                    source_concepts=["COST_OF_REVENUE", "INVENTORY"],
                    source_periods=[current_period.period_key],
                ),
            )

        avg_inv, diag, used_fb, inv_facts = calculate_two_point_average(
            CanonicalConcept.INVENTORY,
            current_period,
            prior_period,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_fact_ids = [cogs_fact.fact_id, *(f.fact_id for f in inv_facts)]
        all_periods = list(
            dict.fromkeys(
                [current_period.period_key, *(f.period.period_key for f in inv_facts)]
            )
        )

        if avg_inv is None or diag is not None and not used_fb:
            return MetricResult(
                metric_id=FundamentalMetricId.INVENTORY_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.NOT_APPLICABLE
                if diag and diag.code == DiagnosticCode.MISSING_REQUIRED_FACT
                else MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[diag] if diag else [],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INVENTORY_TURNOVER_COGS",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["COST_OF_REVENUE", "INVENTORY"],
                    source_periods=all_periods,
                ),
            )

        if avg_inv <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.INVENTORY_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Average Inventory is zero or negative; Inventory Turnover is undefined.",
                        details={"inventory": str(avg_inv)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INVENTORY_TURNOVER_COGS",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["COST_OF_REVENUE", "INVENTORY"],
                    source_periods=all_periods,
                ),
            )

        turnover = cogs_fact.value / avg_inv
        diagnostics = [diag] if diag and used_fb else []
        notes = (
            "Ending point-in-time inventory used under fallback mode."
            if used_fb
            else "Two-point average inventory used."
        )

        return MetricResult(
            metric_id=FundamentalMetricId.INVENTORY_TURNOVER,
            category=MetricCategory.EFFICIENCY,
            status=MetricStatus.VALID,
            value=turnover,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_INVENTORY_TURNOVER_COGS",
                source_fact_ids=all_fact_ids,
                source_concepts=["COST_OF_REVENUE", "INVENTORY"],
                source_periods=all_periods,
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_payables_turnover(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Payables Turnover: Cost of Revenue / Average Accounts Payable.
        """
        cogs_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.COST_OF_REVENUE,
            current_period.period_key,
        )
        if cogs_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.PAYABLES_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Cost of Revenue fact is missing for Payables Turnover.",
                        details={
                            "concept": "COST_OF_REVENUE",
                            "period": current_period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_PAYABLES_TURNOVER",
                    source_concepts=["COST_OF_REVENUE", "ACCOUNTS_PAYABLE"],
                    source_periods=[current_period.period_key],
                ),
            )

        avg_ap, diag, used_fb, ap_facts = calculate_two_point_average(
            CanonicalConcept.ACCOUNTS_PAYABLE,
            current_period,
            prior_period,
            fact_store,
            allow_point_in_time_fallback,
        )

        all_fact_ids = [cogs_fact.fact_id, *(f.fact_id for f in ap_facts)]
        all_periods = list(
            dict.fromkeys(
                [current_period.period_key, *(f.period.period_key for f in ap_facts)]
            )
        )

        if avg_ap is None or diag is not None and not used_fb:
            return MetricResult(
                metric_id=FundamentalMetricId.PAYABLES_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[diag] if diag else [],
                provenance=MetricProvenance(
                    formula_id="FORMULA_PAYABLES_TURNOVER",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["COST_OF_REVENUE", "ACCOUNTS_PAYABLE"],
                    source_periods=all_periods,
                ),
            )

        if avg_ap <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.PAYABLES_TURNOVER,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Average Accounts Payable is zero or negative; Payables Turnover is undefined.",
                        details={"ap": str(avg_ap)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_PAYABLES_TURNOVER",
                    source_fact_ids=all_fact_ids,
                    source_concepts=["COST_OF_REVENUE", "ACCOUNTS_PAYABLE"],
                    source_periods=all_periods,
                ),
            )

        turnover = cogs_fact.value / avg_ap
        diagnostics = [diag] if diag and used_fb else []
        notes = (
            "Ending point-in-time AP used under fallback mode."
            if used_fb
            else "Two-point average AP used."
        )

        return MetricResult(
            metric_id=FundamentalMetricId.PAYABLES_TURNOVER,
            category=MetricCategory.EFFICIENCY,
            status=MetricStatus.VALID,
            value=turnover,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_PAYABLES_TURNOVER",
                source_fact_ids=all_fact_ids,
                source_concepts=["COST_OF_REVENUE", "ACCOUNTS_PAYABLE"],
                source_periods=all_periods,
                methodology_notes=notes,
            ),
        )

    @staticmethod
    def _resolve_days_in_period(period: FinancialPeriod) -> Decimal | None:
        """
        Derive exact days in the reporting duration period from authoritative start and end dates.
        Formula: (period.end_date - period.start_date).days + 1
        Returns None if authoritative duration boundaries are unavailable.
        """
        if period.start_date is not None and period.end_date is not None:
            day_count = (period.end_date - period.start_date).days + 1
            if day_count > 0:
                return Decimal(str(day_count))
        return None

    @classmethod
    def calculate_dso(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Days Sales Outstanding (DSO): (Average AR / Revenue) * days_in_period.
        Requires authoritative period start_date and end_date.
        """
        days_in_period = cls._resolve_days_in_period(current_period)
        if days_in_period is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DAYS_SALES_OUTSTANDING,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Authoritative start and end dates are required to calculate duration-based days metrics.",
                        details={
                            "period": current_period.period_key,
                            "reason": "missing_period_dates",
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DSO_PERIOD_DAYS",
                    source_concepts=["REVENUE", "ACCOUNTS_RECEIVABLE"],
                    source_periods=[current_period.period_key],
                ),
            )

        t_res = cls.calculate_receivables_turnover(
            current_period, prior_period, fact_store, allow_point_in_time_fallback
        )
        if (
            t_res.value is None
            or t_res.status != MetricStatus.VALID
            or t_res.value <= Decimal("0")
        ):
            return MetricResult(
                metric_id=FundamentalMetricId.DAYS_SALES_OUTSTANDING,
                category=MetricCategory.EFFICIENCY,
                status=t_res.status,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=t_res.diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_DSO_PERIOD_DAYS",
                    source_fact_ids=t_res.provenance.source_fact_ids,
                    source_concepts=t_res.provenance.source_concepts,
                    source_periods=t_res.provenance.source_periods,
                ),
            )

        dso = days_in_period / t_res.value
        notes = (
            f"Calculated using authoritative period duration of {days_in_period} days: "
            f"Average AR / Revenue * {days_in_period}."
        )
        if t_res.provenance.methodology_notes:
            notes += f" {t_res.provenance.methodology_notes}"

        return MetricResult(
            metric_id=FundamentalMetricId.DAYS_SALES_OUTSTANDING,
            category=MetricCategory.EFFICIENCY,
            status=MetricStatus.VALID,
            value=dso,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=t_res.diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_DSO_PERIOD_DAYS",
                source_fact_ids=t_res.provenance.source_fact_ids,
                source_concepts=t_res.provenance.source_concepts,
                source_periods=t_res.provenance.source_periods,
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_dio(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Days Inventory Outstanding (DIO): (Average Inventory / Cost of Revenue) * days_in_period.
        Requires authoritative period start_date and end_date.
        """
        days_in_period = cls._resolve_days_in_period(current_period)
        if days_in_period is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DAYS_INVENTORY_OUTSTANDING,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Authoritative start and end dates are required to calculate duration-based days metrics.",
                        details={
                            "period": current_period.period_key,
                            "reason": "missing_period_dates",
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DIO_PERIOD_DAYS",
                    source_concepts=["COST_OF_REVENUE", "INVENTORY"],
                    source_periods=[current_period.period_key],
                ),
            )

        t_res = cls.calculate_inventory_turnover(
            current_period, prior_period, fact_store, allow_point_in_time_fallback
        )
        if (
            t_res.value is None
            or t_res.status != MetricStatus.VALID
            or t_res.value <= Decimal("0")
        ):
            return MetricResult(
                metric_id=FundamentalMetricId.DAYS_INVENTORY_OUTSTANDING,
                category=MetricCategory.EFFICIENCY,
                status=t_res.status,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=t_res.diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_DIO_PERIOD_DAYS",
                    source_fact_ids=t_res.provenance.source_fact_ids,
                    source_concepts=t_res.provenance.source_concepts,
                    source_periods=t_res.provenance.source_periods,
                ),
            )

        dio = days_in_period / t_res.value
        notes = (
            f"Calculated using authoritative period duration of {days_in_period} days: "
            f"Average Inventory / Cost of Revenue * {days_in_period}."
        )
        if t_res.provenance.methodology_notes:
            notes += f" {t_res.provenance.methodology_notes}"

        return MetricResult(
            metric_id=FundamentalMetricId.DAYS_INVENTORY_OUTSTANDING,
            category=MetricCategory.EFFICIENCY,
            status=MetricStatus.VALID,
            value=dio,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=t_res.diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_DIO_PERIOD_DAYS",
                source_fact_ids=t_res.provenance.source_fact_ids,
                source_concepts=t_res.provenance.source_concepts,
                source_periods=t_res.provenance.source_periods,
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_dpo(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Days Payable Outstanding (DPO): (Average Accounts Payable / Cost of Revenue) * days_in_period.
        Requires authoritative period start_date and end_date.
        """
        days_in_period = cls._resolve_days_in_period(current_period)
        if days_in_period is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DAYS_PAYABLE_OUTSTANDING,
                category=MetricCategory.EFFICIENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Authoritative start and end dates are required to calculate duration-based days metrics.",
                        details={
                            "period": current_period.period_key,
                            "reason": "missing_period_dates",
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DPO_PERIOD_DAYS",
                    source_concepts=["COST_OF_REVENUE", "ACCOUNTS_PAYABLE"],
                    source_periods=[current_period.period_key],
                ),
            )

        t_res = cls.calculate_payables_turnover(
            current_period, prior_period, fact_store, allow_point_in_time_fallback
        )
        if (
            t_res.value is None
            or t_res.status != MetricStatus.VALID
            or t_res.value <= Decimal("0")
        ):
            return MetricResult(
                metric_id=FundamentalMetricId.DAYS_PAYABLE_OUTSTANDING,
                category=MetricCategory.EFFICIENCY,
                status=t_res.status,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=current_period,
                diagnostics=t_res.diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_DPO_PERIOD_DAYS",
                    source_fact_ids=t_res.provenance.source_fact_ids,
                    source_concepts=t_res.provenance.source_concepts,
                    source_periods=t_res.provenance.source_periods,
                ),
            )

        dpo = days_in_period / t_res.value
        notes = (
            f"Calculated using authoritative period duration of {days_in_period} days: "
            f"Average AP / Cost of Revenue * {days_in_period}."
        )
        if t_res.provenance.methodology_notes:
            notes += f" {t_res.provenance.methodology_notes}"

        return MetricResult(
            metric_id=FundamentalMetricId.DAYS_PAYABLE_OUTSTANDING,
            category=MetricCategory.EFFICIENCY,
            status=MetricStatus.VALID,
            value=dpo,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=t_res.diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_DPO_PERIOD_DAYS",
                source_fact_ids=t_res.provenance.source_fact_ids,
                source_concepts=t_res.provenance.source_concepts,
                source_periods=t_res.provenance.source_periods,
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_ccc(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
        allow_point_in_time_fallback: bool = False,
    ) -> MetricResult:
        """
        Calculate Cash Conversion Cycle (CCC): DIO + DSO - DPO.
        """
        dso_res = cls.calculate_dso(
            current_period, prior_period, fact_store, allow_point_in_time_fallback
        )
        dio_res = cls.calculate_dio(
            current_period, prior_period, fact_store, allow_point_in_time_fallback
        )
        dpo_res = cls.calculate_dpo(
            current_period, prior_period, fact_store, allow_point_in_time_fallback
        )

        components = [dso_res, dio_res, dpo_res]
        all_facts = list(
            dict.fromkeys(
                fid for r in components for fid in r.provenance.source_fact_ids
            )
        )
        all_concepts = list(
            dict.fromkeys(c for r in components for c in r.provenance.source_concepts)
        )
        all_diags = [d for r in components for d in r.diagnostics]

        for r in components:
            if r.status != MetricStatus.VALID or r.value is None:
                return MetricResult(
                    metric_id=FundamentalMetricId.CASH_CONVERSION_CYCLE,
                    category=MetricCategory.EFFICIENCY,
                    status=r.status,
                    value=None,
                    unit=Unit.RATIO,
                    currency=None,
                    period=current_period,
                    diagnostics=all_diags,
                    provenance=MetricProvenance(
                        formula_id="FORMULA_CASH_CONVERSION_CYCLE",
                        source_fact_ids=all_facts,
                        source_concepts=all_concepts,
                        source_periods=[current_period.period_key],
                    ),
                )

        ccc = dio_res.value + dso_res.value - dpo_res.value
        return MetricResult(
            metric_id=FundamentalMetricId.CASH_CONVERSION_CYCLE,
            category=MetricCategory.EFFICIENCY,
            status=MetricStatus.VALID,
            value=ccc,
            unit=Unit.RATIO,
            currency=None,
            period=current_period,
            diagnostics=all_diags,
            provenance=MetricProvenance(
                formula_id="FORMULA_CASH_CONVERSION_CYCLE",
                source_fact_ids=all_facts,
                source_concepts=all_concepts,
                source_periods=[current_period.period_key],
                methodology_notes=f"Cash Conversion Cycle: DIO ({dio_res.value}) + DSO ({dso_res.value}) - DPO ({dpo_res.value}).",
            ),
        )
