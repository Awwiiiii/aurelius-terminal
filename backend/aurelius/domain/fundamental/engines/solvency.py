"""
aurelius.domain.fundamental.engines.solvency
============================================
Pure calculation engine for solvency and capital structure metrics:
Canonical Gross Debt, Net Debt, Debt-to-Equity, Debt-to-Assets,
Interest Coverage, and Debt/EBITDA ratios.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialFact,
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


class SolvencyEngine:
    """
    Engine calculating solvency and leverage metrics with unified Gross Debt resolution.
    """

    @staticmethod
    def resolve_gross_debt(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> tuple[
        Decimal | None, list[FinancialFact], str, str | None, MetricDiagnostic | None
    ]:
        """
        Resolve unified canonical Gross Debt:
          1. Explicit Short-Term Debt + Long-Term Funded Debt -> sum.
          2. Explicit aggregate interest-bearing Total Debt -> use reported value.
          3. Long-Term Debt only -> use it with SHORT_TERM_DEBT_UNAVAILABLE warning.
          4. None available -> MISSING_REQUIRED_FACT.

        Returns:
          (value, source_facts, formula_id, methodology_notes, diagnostic)
        """
        lt_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.LONG_TERM_DEBT,
            period.period_key,
        )
        st_fact = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            [
                "Current Debt",
                "Short Term Debt",
                "Current Debt And Capital Lease Obligation",
                "Current Portion Of Long Term Debt",
                "Short Term Borrowings",
                "Commercial Paper",
            ],
            period.period_key,
        )

        # Hierarchy 1: Both ST and LT funded debt
        if lt_fact is not None and st_fact is not None:
            total_val = st_fact.value + lt_fact.value
            return (
                total_val,
                [st_fact, lt_fact],
                "FORMULA_GROSS_DEBT_ST_PLUS_LT",
                "Gross Debt calculated as Short-Term Debt + Long-Term Debt.",
                None,
            )

        # Hierarchy 2: Reported Total Debt
        total_debt_fact = fact_store.get_source_fact(
            StatementType.BALANCE_SHEET,
            ["Total Debt", "Total Debt And Capital Lease Obligation"],
            period.period_key,
        )
        if total_debt_fact is not None:
            return (
                total_debt_fact.value,
                [total_debt_fact],
                "FORMULA_GROSS_DEBT_REPORTED_TOTAL",
                "Gross Debt sourced from reported Total Debt line item.",
                None,
            )

        # Hierarchy 3: Long-Term Debt only
        if lt_fact is not None:
            return (
                lt_fact.value,
                [lt_fact],
                "FORMULA_GROSS_DEBT_LT_ONLY",
                "Short-term debt was not separately disclosed; Gross Debt reflects Long-Term Debt only.",
                MetricDiagnostic(
                    code=DiagnosticCode.SHORT_TERM_DEBT_UNAVAILABLE,
                    message="Short-term debt is not separately reported; Gross Debt reflects Long-Term Debt only.",
                    details={"period": period.period_key},
                ),
            )

        # Hierarchy 4: Short-Term Debt only
        if st_fact is not None:
            return (
                st_fact.value,
                [st_fact],
                "FORMULA_GROSS_DEBT_ST_ONLY",
                "Long-term debt was not separately disclosed; Gross Debt reflects Short-Term Debt only.",
                MetricDiagnostic(
                    code=DiagnosticCode.LONG_TERM_DEBT_UNAVAILABLE,
                    message="Long-term debt is not separately reported; Gross Debt reflects Short-Term Debt only.",
                    details={"period": period.period_key},
                ),
            )

        # Hierarchy 5: Missing
        diag = MetricDiagnostic(
            code=DiagnosticCode.MISSING_REQUIRED_FACT,
            message="No debt line items (Long-Term Debt, Short-Term Debt, or Total Debt) found on balance sheet.",
            details={"period": period.period_key},
        )
        return (None, [], "FORMULA_GROSS_DEBT", None, diag)

    @classmethod
    def calculate_gross_debt(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate canonical Gross Debt.
        """
        val, facts, formula_id, notes, diag = cls.resolve_gross_debt(period, fact_store)
        curr = facts[0].currency if facts else None

        if val is None:
            return MetricResult(
                metric_id=FundamentalMetricId.GROSS_DEBT,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=curr,
                period=period,
                diagnostics=[diag] if diag else [],
                provenance=MetricProvenance(
                    formula_id=formula_id,
                    source_concepts=["LONG_TERM_DEBT"],
                    source_periods=[period.period_key],
                ),
            )

        diagnostics = [diag] if diag else []
        return MetricResult(
            metric_id=FundamentalMetricId.GROSS_DEBT,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=val,
            unit=Unit.CURRENCY,
            currency=curr,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id=formula_id,
                source_fact_ids=[f.fact_id for f in facts],
                source_concepts=[f.concept.source_concept for f in facts],
                source_periods=[period.period_key],
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_net_debt(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Net Debt: Gross Debt - (Cash & Equivalents + Short-Term Investments).
        Negative Net Debt (net cash position) is economically valid.
        """
        debt_val, debt_facts, formula_id, notes, debt_diag = cls.resolve_gross_debt(
            period, fact_store
        )
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

        if debt_val is None or cash_fact is None:
            missing = []
            if debt_val is None:
                missing.append("GROSS_DEBT")
            if cash_fact is None:
                missing.append("CASH_AND_EQUIVALENTS")
            return MetricResult(
                metric_id=FundamentalMetricId.NET_DEBT,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=cash_fact.currency if cash_fact else None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for Net Debt: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_DEBT",
                    source_concepts=["GROSS_DEBT", "CASH_AND_EQUIVALENTS"],
                    source_periods=[period.period_key],
                ),
            )

        liquid_pool = cash_fact.value
        all_facts = [*debt_facts, cash_fact]
        all_concepts = [f.concept.source_concept for f in debt_facts] + [
            "CASH_AND_EQUIVALENTS"
        ]

        if st_inv_fact is not None:
            liquid_pool += st_inv_fact.value
            all_facts.append(st_inv_fact)
            all_concepts.append("SHORT_TERM_INVESTMENTS")

        net_debt_val = debt_val - liquid_pool
        diagnostics = [debt_diag] if debt_diag else []

        return MetricResult(
            metric_id=FundamentalMetricId.NET_DEBT,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=net_debt_val,
            unit=Unit.CURRENCY,
            currency=cash_fact.currency,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_NET_DEBT",
                source_fact_ids=[f.fact_id for f in all_facts],
                source_concepts=all_concepts,
                source_periods=[period.period_key],
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_debt_to_equity(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Debt-to-Equity: Gross Debt / Stockholders' Equity.
        Equity <= 0 is DISTORTED with NEGATIVE_OR_ZERO_EQUITY.
        """
        debt_val, debt_facts, formula_id, notes, debt_diag = cls.resolve_gross_debt(
            period, fact_store
        )
        eq_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.STOCKHOLDERS_EQUITY,
            period.period_key,
        )

        missing = []
        if debt_val is None:
            missing.append("GROSS_DEBT")
        if eq_fact is None:
            missing.append("STOCKHOLDERS_EQUITY")

        if missing:
            return MetricResult(
                metric_id=FundamentalMetricId.DEBT_TO_EQUITY,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for Debt-to-Equity: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DEBT_TO_EQUITY",
                    source_concepts=["GROSS_DEBT", "STOCKHOLDERS_EQUITY"],
                    source_periods=[period.period_key],
                ),
            )

        all_facts = [*debt_facts, eq_fact]
        all_concepts = [f.concept.source_concept for f in debt_facts] + [
            "STOCKHOLDERS_EQUITY"
        ]

        if eq_fact.value <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.DEBT_TO_EQUITY,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NEGATIVE_OR_ZERO_EQUITY,
                        message="Stockholders' Equity is zero or negative; Debt-to-Equity is undefined.",
                        details={"equity": str(eq_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DEBT_TO_EQUITY",
                    source_fact_ids=[f.fact_id for f in all_facts],
                    source_concepts=all_concepts,
                    source_periods=[period.period_key],
                ),
            )

        ratio = debt_val / eq_fact.value
        diagnostics = [debt_diag] if debt_diag else []

        return MetricResult(
            metric_id=FundamentalMetricId.DEBT_TO_EQUITY,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=ratio,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_DEBT_TO_EQUITY",
                source_fact_ids=[f.fact_id for f in all_facts],
                source_concepts=all_concepts,
                source_periods=[period.period_key],
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_debt_to_assets(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Debt-to-Assets: Gross Debt / Total Assets.
        """
        debt_val, debt_facts, formula_id, notes, debt_diag = cls.resolve_gross_debt(
            period, fact_store
        )
        assets_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.TOTAL_ASSETS,
            period.period_key,
        )

        missing = []
        if debt_val is None:
            missing.append("GROSS_DEBT")
        if assets_fact is None:
            missing.append("TOTAL_ASSETS")

        if missing:
            return MetricResult(
                metric_id=FundamentalMetricId.DEBT_TO_ASSETS,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for Debt-to-Assets: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DEBT_TO_ASSETS",
                    source_concepts=["GROSS_DEBT", "TOTAL_ASSETS"],
                    source_periods=[period.period_key],
                ),
            )

        all_facts = [*debt_facts, assets_fact]
        all_concepts = [f.concept.source_concept for f in debt_facts] + ["TOTAL_ASSETS"]

        if assets_fact.value <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.DEBT_TO_ASSETS,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="Total Assets is zero or negative; Debt-to-Assets is undefined.",
                        details={"assets": str(assets_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DEBT_TO_ASSETS",
                    source_fact_ids=[f.fact_id for f in all_facts],
                    source_concepts=all_concepts,
                    source_periods=[period.period_key],
                ),
            )

        ratio = debt_val / assets_fact.value
        diagnostics = [debt_diag] if debt_diag else []

        return MetricResult(
            metric_id=FundamentalMetricId.DEBT_TO_ASSETS,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=ratio,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_DEBT_TO_ASSETS",
                source_fact_ids=[f.fact_id for f in all_facts],
                source_concepts=all_concepts,
                source_periods=[period.period_key],
                methodology_notes=notes,
            ),
        )

    @staticmethod
    def calculate_interest_coverage(
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Interest Coverage: Operating Income / Interest Expense.
        Negative EBIT: mathematically valid negative coverage; status=VALID + NEGATIVE_EBIT_WARNING.
        Zero Interest: status=DISTORTED with ZERO_INTEREST_EXPENSE.
        """
        ebit_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT,
            CanonicalConcept.OPERATING_INCOME,
            period.period_key,
        )
        int_fact = fact_store.get_source_fact(
            StatementType.INCOME_STATEMENT,
            [
                "Interest Expense",
                "Interest Expense Non Operating",
                "Interest Expense Operating",
                "Interest Paid",
            ],
            period.period_key,
        )

        missing = []
        if ebit_fact is None:
            missing.append("OPERATING_INCOME")
        if int_fact is None:
            missing.append("INTEREST_EXPENSE")

        if missing:
            return MetricResult(
                metric_id=FundamentalMetricId.INTEREST_COVERAGE,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing inputs for Interest Coverage: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INTEREST_COVERAGE",
                    source_concepts=["OPERATING_INCOME", "INTEREST_EXPENSE"],
                    source_periods=[period.period_key],
                ),
            )

        # Validate interest expense economic sign: negative interest indicates net interest income or inverted sign
        if int_fact.value < Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.INTEREST_COVERAGE,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.INVALID_INTEREST_SIGN,
                        message=(
                            f"Reported interest expense is negative ({int_fact.value}). "
                            "Interest coverage requires positive borrowing interest expense; "
                            "negative value indicates net interest income or anomalous sign reporting."
                        ),
                        details={"interest": str(int_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INTEREST_COVERAGE",
                    source_fact_ids=[ebit_fact.fact_id, int_fact.fact_id],
                    source_concepts=[
                        "OPERATING_INCOME",
                        int_fact.concept.source_concept,
                    ],
                    source_periods=[period.period_key],
                    methodology_notes=f"Reported {int_fact.concept.source_concept} was negative ({int_fact.value}); calculation rejected.",
                ),
            )

        if int_fact.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.INTEREST_COVERAGE,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_INTEREST_EXPENSE,
                        message="Interest expense is zero; Interest Coverage cannot be computed.",
                        details={"interest": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_INTEREST_COVERAGE",
                    source_fact_ids=[ebit_fact.fact_id, int_fact.fact_id],
                    source_concepts=[
                        "OPERATING_INCOME",
                        int_fact.concept.source_concept,
                    ],
                    source_periods=[period.period_key],
                ),
            )

        coverage = ebit_fact.value / int_fact.value
        diagnostics = []
        if ebit_fact.value < Decimal("0"):
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.NEGATIVE_EBIT_WARNING,
                    message="Operating income is negative; coverage is negative and indicates operational inability to service debt.",
                    details={"ebit": str(ebit_fact.value)},
                )
            )

        return MetricResult(
            metric_id=FundamentalMetricId.INTEREST_COVERAGE,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=coverage,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_INTEREST_COVERAGE",
                source_fact_ids=[ebit_fact.fact_id, int_fact.fact_id],
                source_concepts=["OPERATING_INCOME", int_fact.concept.source_concept],
                source_periods=[period.period_key],
            ),
        )

    @classmethod
    def calculate_debt_to_ebitda(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Debt-to-EBITDA: Gross Debt / Reported EBITDA.
        Requires provider-reported EBITDA. Never synthesized in M7A.
        EBITDA <= 0 is DISTORTED with NEGATIVE_OR_ZERO_EBITDA.
        """
        debt_val, debt_facts, formula_id, notes, debt_diag = cls.resolve_gross_debt(
            period, fact_store
        )
        ebitda_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.EBITDA, period.period_key
        )

        if ebitda_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DEBT_TO_EBITDA,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_REPORTED_EBITDA_RESTRICTION,
                        message="EBITDA is not reported directly by the provider; Debt/EBITDA is restricted.",
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DEBT_TO_EBITDA_REPORTED",
                    source_concepts=["GROSS_DEBT", "EBITDA"],
                    source_periods=[period.period_key],
                ),
            )

        if debt_val is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DEBT_TO_EBITDA,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message="Gross Debt could not be resolved for Debt/EBITDA.",
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DEBT_TO_EBITDA_REPORTED",
                    source_concepts=["GROSS_DEBT", "EBITDA"],
                    source_periods=[period.period_key],
                ),
            )

        all_facts = [*debt_facts, ebitda_fact]
        all_concepts = [f.concept.source_concept for f in debt_facts] + ["EBITDA"]

        if ebitda_fact.value <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.DEBT_TO_EBITDA,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NEGATIVE_OR_ZERO_EBITDA,
                        message="Reported EBITDA is zero or negative; Debt/EBITDA is economically distorted.",
                        details={"ebitda": str(ebitda_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DEBT_TO_EBITDA_REPORTED",
                    source_fact_ids=[f.fact_id for f in all_facts],
                    source_concepts=all_concepts,
                    source_periods=[period.period_key],
                ),
            )

        ratio = debt_val / ebitda_fact.value
        diagnostics = [debt_diag] if debt_diag else []

        return MetricResult(
            metric_id=FundamentalMetricId.DEBT_TO_EBITDA,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=ratio,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_DEBT_TO_EBITDA_REPORTED",
                source_fact_ids=[f.fact_id for f in all_facts],
                source_concepts=all_concepts,
                source_periods=[period.period_key],
                methodology_notes=notes,
            ),
        )

    @classmethod
    def calculate_net_debt_to_ebitda(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Net Debt-to-EBITDA: Net Debt / Reported EBITDA.
        Requires provider-reported EBITDA. Never synthesized in M7A.
        EBITDA <= 0 is DISTORTED with NEGATIVE_OR_ZERO_EBITDA.
        """
        net_debt_res = cls.calculate_net_debt(period, fact_store)
        ebitda_fact = fact_store.get_canonical_fact(
            StatementType.INCOME_STATEMENT, CanonicalConcept.EBITDA, period.period_key
        )

        if ebitda_fact is None:
            return MetricResult(
                metric_id=FundamentalMetricId.NET_DEBT_TO_EBITDA,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NON_REPORTED_EBITDA_RESTRICTION,
                        message="EBITDA is not reported directly by the provider; Net Debt/EBITDA is restricted.",
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_DEBT_TO_EBITDA_REPORTED",
                    source_concepts=["NET_DEBT", "EBITDA"],
                    source_periods=[period.period_key],
                ),
            )

        if net_debt_res.value is None or net_debt_res.status != MetricStatus.VALID:
            return MetricResult(
                metric_id=FundamentalMetricId.NET_DEBT_TO_EBITDA,
                category=MetricCategory.SOLVENCY,
                status=net_debt_res.status,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=net_debt_res.diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_DEBT_TO_EBITDA_REPORTED",
                    source_concepts=["NET_DEBT", "EBITDA"],
                    source_periods=[period.period_key],
                ),
            )

        if ebitda_fact.value <= Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.NET_DEBT_TO_EBITDA,
                category=MetricCategory.SOLVENCY,
                status=MetricStatus.DISTORTED,
                value=None,
                unit=Unit.RATIO,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.NEGATIVE_OR_ZERO_EBITDA,
                        message="Reported EBITDA is zero or negative; Net Debt/EBITDA is economically distorted.",
                        details={"ebitda": str(ebitda_fact.value)},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_NET_DEBT_TO_EBITDA_REPORTED",
                    source_fact_ids=[
                        *net_debt_res.provenance.source_fact_ids,
                        ebitda_fact.fact_id,
                    ],
                    source_concepts=[
                        *net_debt_res.provenance.source_concepts,
                        "EBITDA",
                    ],
                    source_periods=[period.period_key],
                ),
            )

        ratio = net_debt_res.value / ebitda_fact.value
        return MetricResult(
            metric_id=FundamentalMetricId.NET_DEBT_TO_EBITDA,
            category=MetricCategory.SOLVENCY,
            status=MetricStatus.VALID,
            value=ratio,
            unit=Unit.RATIO,
            currency=None,
            period=period,
            diagnostics=net_debt_res.diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_NET_DEBT_TO_EBITDA_REPORTED",
                source_fact_ids=[
                    *net_debt_res.provenance.source_fact_ids,
                    ebitda_fact.fact_id,
                ],
                source_concepts=[*net_debt_res.provenance.source_concepts, "EBITDA"],
                source_periods=[period.period_key],
            ),
        )
