"""
aurelius.domain.fundamental.engines.cash_flow
=============================================
Pure calculation engine for cash flow and free cash flow metrics:
Operating Cash Flow, Normalized CapEx, Primary Free Cash Flow,
FCF Margin, FCF Conversion, and CFO / Net Income.
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
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore


class CashFlowEngine:
    """
    Engine calculating cash generation and free cash flow conversion metrics.
    """

    @staticmethod
    def calculate_operating_cash_flow(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve canonical Operating Cash Flow (CFO).
        """
        cfo_fact = fact_store.get_canonical_fact(
            StatementType.CASH_FLOW,
            CanonicalConcept.OPERATING_CASH_FLOW,
            period.period_key,
        )
        if cfo_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_CASH_FLOW,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Operating Cash Flow fact is missing.",
                        details={
                            "concept": "OPERATING_CASH_FLOW",
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="REPORTED_OPERATING_CASH_FLOW",
                    source_concepts=["OPERATING_CASH_FLOW"],
                    source_periods=[period.period_key],
                ),
                is_derived=False,
            )

        return MetricResult(
            metric_id=FundamentalMetricId.OPERATING_CASH_FLOW,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=cfo_fact.value,
            unit=Unit.CURRENCY,
            currency=cfo_fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="REPORTED_OPERATING_CASH_FLOW",
                source_fact_ids=[cfo_fact.fact_id],
                source_concepts=["OPERATING_CASH_FLOW"],
                source_periods=[period.period_key],
            ),
            is_derived=False,
        )

    @staticmethod
    def calculate_capital_expenditures(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Retrieve Capital Expenditures normalized to positive economic magnitude
        while preserving original source sign in provenance notes.
        """
        capex_fact = fact_store.get_canonical_fact(
            StatementType.CASH_FLOW,
            CanonicalConcept.CAPITAL_EXPENDITURES,
            period.period_key,
        )
        if capex_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.CAPITAL_EXPENDITURES,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Capital Expenditures fact is missing.",
                        details={
                            "concept": "CAPITAL_EXPENDITURES",
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="REPORTED_CAPITAL_EXPENDITURES",
                    source_concepts=["CAPITAL_EXPENDITURES"],
                    source_periods=[period.period_key],
                ),
                is_derived=False,
            )

        # Normalize to positive economic outflow magnitude
        magnitude = abs(capex_fact.value)
        return MetricResult(
            metric_id=FundamentalMetricId.CAPITAL_EXPENDITURES,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=magnitude,
            unit=Unit.CURRENCY,
            currency=capex_fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="NORMALIZED_CAPITAL_EXPENDITURES",
                source_fact_ids=[capex_fact.fact_id],
                source_concepts=["CAPITAL_EXPENDITURES"],
                source_periods=[period.period_key],
                methodology_notes=f"Reported value was {capex_fact.value}; normalized to positive economic magnitude {magnitude}.",
            ),
            is_derived=True,
        )

    @classmethod
    def calculate_free_cash_flow(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate AURELIUS Primary Free Cash Flow: Operating Cash Flow - abs(Capital Expenditures).
        """
        cfo_fact = fact_store.get_canonical_fact(
            StatementType.CASH_FLOW,
            CanonicalConcept.OPERATING_CASH_FLOW,
            period.period_key,
        )
        capex_fact = fact_store.get_canonical_fact(
            StatementType.CASH_FLOW,
            CanonicalConcept.CAPITAL_EXPENDITURES,
            period.period_key,
        )

        missing = []
        if cfo_fact is None:
            missing.append("OPERATING_CASH_FLOW")
        if capex_fact is None:
            missing.append("CAPITAL_EXPENDITURES")

        if missing:
            return MetricResult(
                metric_id=FundamentalMetricId.FREE_CASH_FLOW,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=cfo_fact.currency
                if cfo_fact
                else (capex_fact.currency if capex_fact else None),
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for Free Cash Flow: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_AURELIUS_PRIMARY_FCF",
                    source_concepts=["OPERATING_CASH_FLOW", "CAPITAL_EXPENDITURES"],
                    source_periods=[period.period_key],
                ),
            )

        fcf_val = cfo_fact.value - abs(capex_fact.value)
        return MetricResult(
            metric_id=FundamentalMetricId.FREE_CASH_FLOW,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=fcf_val,
            unit=Unit.CURRENCY,
            currency=cfo_fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_AURELIUS_PRIMARY_FCF",
                source_fact_ids=[cfo_fact.fact_id, capex_fact.fact_id],
                source_concepts=["OPERATING_CASH_FLOW", "CAPITAL_EXPENDITURES"],
                source_periods=[period.period_key],
                methodology_notes="AURELIUS canonical primary FCF convention: Operating Cash Flow minus absolute Capital Expenditures.",
            ),
        )

    @classmethod
    def calculate_fcf_margin(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Free Cash Flow Margin: Free Cash Flow / Revenue.
        """
        fcf_res = cls.calculate_free_cash_flow(period, fact_store)
        rev_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.REVENUE, period.period_key
        )

        if (
            rev_fact is None
            or fcf_res.value is None
            or fcf_res.status != MetricStatus.VALID
        ):
            missing = []
            if rev_fact is None:
                missing.append("REVENUE")
            if fcf_res.status != MetricStatus.VALID:
                missing.append("FREE_CASH_FLOW")
            return MetricResult(
                metric_id=FundamentalMetricId.FCF_MARGIN,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for FCF Margin: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_FCF_MARGIN",
                    source_concepts=["FREE_CASH_FLOW", "REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        if rev_fact.value <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.FCF_MARGIN,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_OR_NEGATIVE_REVENUE,
                        message="Revenue is zero or negative; FCF Margin is undefined.",
                        details={"revenue": str(rev_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_FCF_MARGIN",
                    source_fact_ids=[
                        *fcf_res.provenance.source_fact_ids,
                        rev_fact.fact_id,
                    ],
                    source_concepts=[*fcf_res.provenance.source_concepts, "REVENUE"],
                    source_periods=[period.period_key],
                ),
            )

        margin = fcf_res.value / rev_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.FCF_MARGIN,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=margin,
            unit=Unit.PERCENT,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_FCF_MARGIN",
                source_fact_ids=[*fcf_res.provenance.source_fact_ids, rev_fact.fact_id],
                source_concepts=[*fcf_res.provenance.source_concepts, "REVENUE"],
                source_periods=[period.period_key],
            ),
        )

    @classmethod
    def calculate_fcf_conversion(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate FCF Conversion: Free Cash Flow / Net Income.
        Net Income <= 0 handled with ZERO_DIVISION or NEGATIVE_NET_INCOME.
        """
        fcf_res = cls.calculate_free_cash_flow(period, fact_store)
        ni_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.NET_INCOME,
            period.period_key,
        )

        if (
            ni_fact is None
            or fcf_res.value is None
            or fcf_res.status != MetricStatus.VALID
        ):
            missing = []
            if ni_fact is None:
                missing.append("NET_INCOME")
            if fcf_res.status != MetricStatus.VALID:
                missing.append("FREE_CASH_FLOW")
            return MetricResult(
                metric_id=FundamentalMetricId.FCF_CONVERSION,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for FCF Conversion: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_FCF_CONVERSION",
                    source_concepts=["FREE_CASH_FLOW", "NET_INCOME"],
                    source_periods=[period.period_key],
                ),
            )

        all_facts = [*fcf_res.provenance.source_fact_ids, ni_fact.fact_id]
        all_concepts = [*fcf_res.provenance.source_concepts, "NET_INCOME"]

        if ni_fact.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.FCF_CONVERSION,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Net income is zero; FCF Conversion cannot be calculated.",
                        details={"net_income": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_FCF_CONVERSION",
                    source_fact_ids=all_facts,
                    source_concepts=all_concepts,
                    source_periods=[period.period_key],
                ),
            )

        if ni_fact.value < Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.FCF_CONVERSION,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.PERCENT,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NEGATIVE_NET_INCOME,
                        message="Net income is negative; FCF Conversion percentage is distorted.",
                        details={"net_income": str(ni_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_FCF_CONVERSION",
                    source_fact_ids=all_facts,
                    source_concepts=all_concepts,
                    source_periods=[period.period_key],
                ),
            )

        conv = fcf_res.value / ni_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.FCF_CONVERSION,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=conv,
            unit=Unit.PERCENT,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_FCF_CONVERSION",
                source_fact_ids=all_facts,
                source_concepts=all_concepts,
                source_periods=[period.period_key],
            ),
        )

    @staticmethod
    def calculate_cfo_to_net_income(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Operating Cash Flow / Net Income ratio.
        Net Income <= 0 handled with ZERO_DIVISION or NEGATIVE_NET_INCOME.
        """
        cfo_fact = fact_store.get_canonical_fact(
            StatementType.CASH_FLOW,
            CanonicalConcept.OPERATING_CASH_FLOW,
            period.period_key,
        )
        ni_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.NET_INCOME,
            period.period_key,
        )

        missing = []
        if cfo_fact is None:
            missing.append("OPERATING_CASH_FLOW")
        if ni_fact is None:
            missing.append("NET_INCOME")

        if missing:
            return MetricResult(
                metric_id=FundamentalMetricId.CFO_TO_NET_INCOME,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for CFO/Net Income: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CFO_TO_NET_INCOME",
                    source_concepts=["OPERATING_CASH_FLOW", "NET_INCOME"],
                    source_periods=[period.period_key],
                ),
            )

        all_facts = [cfo_fact.fact_id, ni_fact.fact_id]
        all_concepts = ["OPERATING_CASH_FLOW", "NET_INCOME"]

        if ni_fact.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.CFO_TO_NET_INCOME,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Net income is zero; CFO/Net Income is undefined.",
                        details={"net_income": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CFO_TO_NET_INCOME",
                    source_fact_ids=all_facts,
                    source_concepts=all_concepts,
                    source_periods=[period.period_key],
                ),
            )

        if ni_fact.value < Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.CFO_TO_NET_INCOME,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NEGATIVE_NET_INCOME,
                        message="Net income is negative; CFO/Net Income is distorted.",
                        details={"net_income": str(ni_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CFO_TO_NET_INCOME",
                    source_fact_ids=all_facts,
                    source_concepts=all_concepts,
                    source_periods=[period.period_key],
                ),
            )

        ratio = cfo_fact.value / ni_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.CFO_TO_NET_INCOME,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=ratio,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_CFO_TO_NET_INCOME",
                source_fact_ids=all_facts,
                source_concepts=all_concepts,
                source_periods=[period.period_key],
            ),
        )
