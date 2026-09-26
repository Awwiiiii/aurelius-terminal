"""
aurelius.domain.fundamental.engines.liquidity
=============================================
Pure calculation engine for short-term liquidity metrics: Working Capital,
Current Ratio, Quick Ratio, and Cash Ratio.
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


class LiquidityEngine:
    """
    Engine calculating balance-sheet liquidity metrics.
    """

    @staticmethod
    def calculate_working_capital(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Working Capital: Current Assets - Current Liabilities.
        """
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

        missing = []
        if ca_fact is None:
            missing.append("CURRENT_ASSETS")
        if cl_fact is None:
            missing.append("CURRENT_LIABILITIES")

        if missing:
            code = (
                DiagnosticCode.UNCLASSIFIED_BALANCE_SHEET
                if len(missing) == 2
                else DiagnosticCode.MISSING_REQUIRED_FACT
            )
            msg = (
                "Balance sheet does not classify current assets/liabilities (common in financial institutions)."
                if code == DiagnosticCode.UNCLASSIFIED_BALANCE_SHEET
                else f"Missing required liquidity inputs: {', '.join(missing)}."
            )
            return MetricResult(
                metric_id=FundamentalMetricId.WORKING_CAPITAL,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.NOT_APPLICABLE
                if code == DiagnosticCode.UNCLASSIFIED_BALANCE_SHEET
                else MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=ca_fact.currency
                if ca_fact
                else (cl_fact.currency if cl_fact else None),
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=code,
                        message=msg,
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_WORKING_CAPITAL",
                    source_concepts=["CURRENT_ASSETS", "CURRENT_LIABILITIES"],
                    source_periods=[period.period_key],
                ),
            )

        wc_val = ca_fact.value - cl_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.WORKING_CAPITAL,
            category=MetricCategory.LIQUIDITY,
            status=MetricStatus.VALID,
            value=wc_val,
            unit=Unit.CURRENCY,
            currency=ca_fact.currency,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_WORKING_CAPITAL",
                source_fact_ids=[ca_fact.fact_id, cl_fact.fact_id],
                source_concepts=["CURRENT_ASSETS", "CURRENT_LIABILITIES"],
                source_periods=[period.period_key],
            ),
        )

    @staticmethod
    def calculate_current_ratio(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Current Ratio: Current Assets / Current Liabilities.
        """
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

        missing = []
        if ca_fact is None:
            missing.append("CURRENT_ASSETS")
        if cl_fact is None:
            missing.append("CURRENT_LIABILITIES")

        if missing:
            code = (
                DiagnosticCode.UNCLASSIFIED_BALANCE_SHEET
                if len(missing) == 2
                else DiagnosticCode.MISSING_REQUIRED_FACT
            )
            msg = (
                "Unclassified balance sheet does not report current assets/liabilities."
                if code == DiagnosticCode.UNCLASSIFIED_BALANCE_SHEET
                else f"Missing inputs for Current Ratio: {', '.join(missing)}."
            )
            return MetricResult(
                metric_id=FundamentalMetricId.CURRENT_RATIO,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.NOT_APPLICABLE
                if code == DiagnosticCode.UNCLASSIFIED_BALANCE_SHEET
                else MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=code,
                        message=msg,
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CURRENT_RATIO",
                    source_concepts=["CURRENT_ASSETS", "CURRENT_LIABILITIES"],
                    source_periods=[period.period_key],
                ),
            )

        if cl_fact.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.CURRENT_RATIO,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Current liabilities are zero; Current Ratio is undefined.",
                        details={"current_liabilities": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CURRENT_RATIO",
                    source_fact_ids=[ca_fact.fact_id, cl_fact.fact_id],
                    source_concepts=["CURRENT_ASSETS", "CURRENT_LIABILITIES"],
                    source_periods=[period.period_key],
                ),
            )

        ratio = ca_fact.value / cl_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.CURRENT_RATIO,
            category=MetricCategory.LIQUIDITY,
            status=MetricStatus.VALID,
            value=ratio,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_CURRENT_RATIO",
                source_fact_ids=[ca_fact.fact_id, cl_fact.fact_id],
                source_concepts=["CURRENT_ASSETS", "CURRENT_LIABILITIES"],
                source_periods=[period.period_key],
            ),
        )

    @staticmethod
    def calculate_quick_ratio(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Quick Ratio: (Cash + Short-Term Investments + Accounts Receivable) / Current Liabilities.
        """
        cash_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
            period.period_key,
        )
        st_inv_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.SHORT_TERM_INVESTMENTS,
            period.period_key,
        )
        ar_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.ACCOUNTS_RECEIVABLE,
            period.period_key,
        )
        cl_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_LIABILITIES,
            period.period_key,
        )

        if cl_fact is None or (cash_fact is None and ar_fact is None):
            missing = []
            if cl_fact is None:
                missing.append("CURRENT_LIABILITIES")
            if cash_fact is None:
                missing.append("CASH_AND_EQUIVALENTS")
            if ar_fact is None:
                missing.append("ACCOUNTS_RECEIVABLE")
            return MetricResult(
                metric_id=FundamentalMetricId.QUICK_RATIO,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for Quick Ratio: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_QUICK_RATIO",
                    source_concepts=[
                        "CASH_AND_EQUIVALENTS",
                        "SHORT_TERM_INVESTMENTS",
                        "ACCOUNTS_RECEIVABLE",
                        "CURRENT_LIABILITIES",
                    ],
                    source_periods=[period.period_key],
                ),
            )

        if cl_fact.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.QUICK_RATIO,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Current liabilities are zero; Quick Ratio is undefined.",
                        details={"current_liabilities": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_QUICK_RATIO",
                    source_concepts=["CASH_AND_EQUIVALENTS", "CURRENT_LIABILITIES"],
                    source_periods=[period.period_key],
                ),
            )

        liquid_pool = Decimal("0")
        source_facts = [cl_fact]
        source_concepts = ["CURRENT_LIABILITIES"]

        if cash_fact is not None:
            liquid_pool += cash_fact.value
            source_facts.append(cash_fact)
            source_concepts.append("CASH_AND_EQUIVALENTS")
        if st_inv_fact is not None:
            liquid_pool += st_inv_fact.value
            source_facts.append(st_inv_fact)
            source_concepts.append("SHORT_TERM_INVESTMENTS")
        if ar_fact is not None:
            liquid_pool += ar_fact.value
            source_facts.append(ar_fact)
            source_concepts.append("ACCOUNTS_RECEIVABLE")

        ratio = liquid_pool / cl_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.QUICK_RATIO,
            category=MetricCategory.LIQUIDITY,
            status=MetricStatus.VALID,
            value=ratio,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_QUICK_RATIO",
                source_fact_ids=[f.fact_id for f in source_facts],
                source_concepts=source_concepts,
                source_periods=[period.period_key],
            ),
        )

    @staticmethod
    def calculate_cash_ratio(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Cash Ratio: (Cash + Short-Term Investments) / Current Liabilities.
        """
        cash_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
            period.period_key,
        )
        st_inv_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.SHORT_TERM_INVESTMENTS,
            period.period_key,
        )
        cl_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CURRENT_LIABILITIES,
            period.period_key,
        )

        if cl_fact is None or cash_fact is None:
            missing = []
            if cl_fact is None:
                missing.append("CURRENT_LIABILITIES")
            if cash_fact is None:
                missing.append("CASH_AND_EQUIVALENTS")
            return MetricResult(
                metric_id=FundamentalMetricId.CASH_RATIO,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for Cash Ratio: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CASH_RATIO",
                    source_concepts=["CASH_AND_EQUIVALENTS", "CURRENT_LIABILITIES"],
                    source_periods=[period.period_key],
                ),
            )

        if cl_fact.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.CASH_RATIO,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Current liabilities are zero; Cash Ratio is undefined.",
                        details={"current_liabilities": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_CASH_RATIO",
                    source_fact_ids=[cash_fact.fact_id, cl_fact.fact_id],
                    source_concepts=["CASH_AND_EQUIVALENTS", "CURRENT_LIABILITIES"],
                    source_periods=[period.period_key],
                ),
            )

        cash_pool = cash_fact.value
        source_facts = [cl_fact, cash_fact]
        source_concepts = ["CURRENT_LIABILITIES", "CASH_AND_EQUIVALENTS"]

        if st_inv_fact is not None:
            cash_pool += st_inv_fact.value
            source_facts.append(st_inv_fact)
            source_concepts.append("SHORT_TERM_INVESTMENTS")

        ratio = cash_pool / cl_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.CASH_RATIO,
            category=MetricCategory.LIQUIDITY,
            status=MetricStatus.VALID,
            value=ratio,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_CASH_RATIO",
                source_fact_ids=[f.fact_id for f in source_facts],
                source_concepts=source_concepts,
                source_periods=[period.period_key],
            ),
        )
