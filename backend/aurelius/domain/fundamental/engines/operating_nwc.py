"""
aurelius.domain.fundamental.engines.operating_nwc
=================================================
Pure calculation engine for Non-Cash Operating Working Capital (NWC)
and Change in Working Capital (Delta NWC).

Formulas:
  Operating Current Assets = Current Assets - Cash & Equivalents - Short-Term Investments
  Operating Current Liabilities = Current Liabilities - Short-Term Debt
  Operating NWC = Operating Current Assets - Operating Current Liabilities
  Delta NWC = NWC(t) - NWC(t-1)

Key Invariants:
  - Applicability is determined strictly from balance-sheet structure/concepts,
    never from provider sector/industry strings.
  - Entities with unclassified balance sheets (e.g. banks, insurers) are NOT_APPLICABLE.
  - Negative operating NWC is valid (accompanied by NEGATIVE_OPERATING_NWC_NOTE).
  - Missing facts are NEVER converted to zero; they result in explicit UNAVAILABLE status.
  - Exact Decimal arithmetic end-to-end with complete provenance.
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


class OperatingNWCEngine:
    """
    Engine calculating Non-Cash Operating Working Capital and Delta NWC.
    """

    METHODOLOGY_VERSION = "1.0.0"

    @classmethod
    def calculate_operating_nwc(
        cls,
        period: FinancialPeriod,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Non-Cash Operating Working Capital (NWC):
          Operating Current Assets - Operating Current Liabilities.

        Applicability:
          - If both Current Assets and Current Liabilities are absent from the balance sheet,
            the entity is classified as unclassified/financial (NOT_APPLICABLE).
          - If one is present and the other missing, UNAVAILABLE with MISSING_REQUIRED_FACT.
          - Negative NWC is valid with NEGATIVE_OPERATING_NWC_NOTE.
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

        # Check for unclassified balance sheet
        if ca_fact is None and cl_fact is None:
            # Check for financial/banking lines
            banking_fact = fact_store.get_source_fact(
                StatementType.BALANCE_SHEET,
                [
                    "Total Deposits",
                    "Deposits",
                    "Loans And Advances",
                    "Net Loans",
                    "Policy Liabilities",
                    "Insurance Reserves",
                ],
                period.period_key,
            )
            diag_code = (
                DiagnosticCode.FINANCIAL_ENTITY_EXEMPTION
                if banking_fact is not None
                else DiagnosticCode.UNCLASSIFIED_BALANCE_SHEET
            )
            diag_msg = (
                "Financial institution operates with an unclassified balance sheet; "
                "Operating NWC is not applicable."
                if banking_fact is not None
                else "Balance sheet is unclassified (lacks Current Assets and Current Liabilities); "
                "Operating NWC is not applicable."
            )
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_NWC,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.NOT_APPLICABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=diag_code,
                        message=diag_msg,
                        details={"period": period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_OPERATING_NWC_UNCLASSIFIED_EXEMPT",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["CURRENT_ASSETS", "CURRENT_LIABILITIES"],
                    source_periods=[period.period_key],
                    methodology_notes="Unclassified balance sheet structure detected; Operating NWC not applicable.",
                ),
            )

        if ca_fact is None or cl_fact is None:
            missing = []
            if ca_fact is None:
                missing.append("CURRENT_ASSETS")
            if cl_fact is None:
                missing.append("CURRENT_LIABILITIES")
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_NWC,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=ca_fact.currency
                if ca_fact
                else (cl_fact.currency if cl_fact else None),
                period=period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing classified balance-sheet concept(s) for Operating NWC: {', '.join(missing)}.",
                        details={
                            "missing": ", ".join(missing),
                            "period": period.period_key,
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_OPERATING_NWC_DEDUCTIVE_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=missing,
                    source_periods=[period.period_key],
                ),
            )

        source_facts: list[FinancialFact] = [ca_fact, cl_fact]
        source_concepts: list[str] = ["CURRENT_ASSETS", "CURRENT_LIABILITIES"]
        diagnostics: list[MetricDiagnostic] = []

        # Deduct Cash & Equivalents
        cash_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.CASH_AND_EQUIVALENTS,
            period.period_key,
        )
        cash_val = Decimal(0)
        if cash_fact is not None:
            cash_val += cash_fact.value
            source_facts.append(cash_fact)
            source_concepts.append("CASH_AND_EQUIVALENTS")

        # Deduct Short-Term Investments if distinct
        sti_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET,
            CanonicalConcept.SHORT_TERM_INVESTMENTS,
            period.period_key,
        )
        sti_val = Decimal(0)
        if sti_fact is not None:
            sti_val += sti_fact.value
            source_facts.append(sti_fact)
            source_concepts.append("SHORT_TERM_INVESTMENTS")

        operating_ca = ca_fact.value - (cash_val + sti_val)

        # Deduct Short-Term Debt from Current Liabilities
        st_debt_fact = fact_store.get_source_fact(
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
        st_debt_val = Decimal(0)
        if st_debt_fact is not None:
            st_debt_val = st_debt_fact.value
            source_facts.append(st_debt_fact)
            source_concepts.append(st_debt_fact.concept.source_concept)
        else:
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.SHORT_TERM_DEBT_UNAVAILABLE,
                    message="Short-term debt was not separately disclosed; operating current liabilities reflects total current liabilities.",
                    details={"period": period.period_key},
                )
            )

        operating_cl = cl_fact.value - st_debt_val
        nwc_val = operating_ca - operating_cl

        if nwc_val < 0:
            diagnostics.append(
                MetricDiagnostic(
                    code=DiagnosticCode.NEGATIVE_OPERATING_NWC_NOTE,
                    message="Negative operating working capital observed: company operations are partially financed by supplier/operating liabilities.",
                    details={
                        "operating_nwc": str(nwc_val),
                        "period": period.period_key,
                    },
                )
            )

        return MetricResult(
            metric_id=FundamentalMetricId.OPERATING_NWC,
            category=MetricCategory.LIQUIDITY,
            status=MetricStatus.VALID,
            value=nwc_val,
            unit=Unit.CURRENCY,
            currency=ca_fact.currency,
            period=period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_OPERATING_NWC_DEDUCTIVE_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[f.fact_id for f in source_facts],
                source_concepts=source_concepts,
                source_periods=[period.period_key],
                methodology_notes=(
                    f"Operating NWC = (Current Assets {ca_fact.value} - Cash {cash_val} - STI {sti_val}) "
                    f"- (Current Liabilities {cl_fact.value} - ST Debt {st_debt_val}) = {nwc_val}."
                ),
            ),
        )

    @classmethod
    def calculate_delta_nwc(
        cls,
        current_period: FinancialPeriod,
        prior_period: FinancialPeriod | None,
        fact_store: MultiPeriodFactStore,
    ) -> MetricResult:
        """
        Calculate Change in Non-Cash Operating Working Capital:
          Delta NWC = NWC(t) - NWC(t-1).

        For Annual: FY(t) vs FY(t-1).
        For Quarterly: Q(t) vs Q(t-1).
        For TTM: Q(t) vs Q(t-4) (1-year interval).

        Interpretation:
          Delta NWC > 0: Cash investment / drag (reduces cash flow).
          Delta NWC < 0: Cash release (increases cash flow).
        """
        curr_nwc = cls.calculate_operating_nwc(current_period, fact_store)
        if curr_nwc.status != MetricStatus.VALID or curr_nwc.value is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DELTA_NWC,
                category=MetricCategory.LIQUIDITY,
                status=curr_nwc.status,
                value=None,
                unit=Unit.CURRENCY,
                currency=curr_nwc.currency,
                period=current_period,
                diagnostics=curr_nwc.diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_DELTA_NWC_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_concepts=["OPERATING_NWC"],
                    source_periods=[current_period.period_key],
                    methodology_notes="Current period Operating NWC unavailable or not applicable.",
                ),
            )

        if prior_period is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DELTA_NWC,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=curr_nwc.currency,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_PRIOR_PERIOD,
                        message="Prior comparison period is unavailable for Delta NWC computation.",
                        details={"period": current_period.period_key},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DELTA_NWC_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=curr_nwc.provenance.source_fact_ids,
                    source_concepts=["OPERATING_NWC"],
                    source_periods=[current_period.period_key],
                    methodology_notes="Prior comparison period not provided.",
                ),
            )

        prior_nwc = cls.calculate_operating_nwc(prior_period, fact_store)
        if prior_nwc.status != MetricStatus.VALID or prior_nwc.value is None:
            return MetricResult(
                metric_id=FundamentalMetricId.DELTA_NWC,
                category=MetricCategory.LIQUIDITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=curr_nwc.currency,
                period=current_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_PRIOR_PERIOD,
                        message=f"Prior period Operating NWC ({prior_period.period_key}) is unavailable.",
                        details={"prior_period": prior_period.period_key},
                    ),
                    *prior_nwc.diagnostics,
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_DELTA_NWC_V1",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=curr_nwc.provenance.source_fact_ids,
                    source_concepts=["OPERATING_NWC"],
                    source_periods=[current_period.period_key, prior_period.period_key],
                    methodology_notes="Prior period Operating NWC could not be calculated.",
                ),
            )

        delta_val = curr_nwc.value - prior_nwc.value

        all_fact_ids = list(
            dict.fromkeys(
                curr_nwc.provenance.source_fact_ids
                + prior_nwc.provenance.source_fact_ids
            )
        )
        all_concepts = list(
            dict.fromkeys(
                curr_nwc.provenance.source_concepts
                + prior_nwc.provenance.source_concepts
            )
        )

        return MetricResult(
            metric_id=FundamentalMetricId.DELTA_NWC,
            category=MetricCategory.LIQUIDITY,
            status=MetricStatus.VALID,
            value=delta_val,
            unit=Unit.CURRENCY,
            currency=curr_nwc.currency,
            period=current_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_DELTA_NWC_V1",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=all_fact_ids,
                source_concepts=all_concepts,
                source_periods=[current_period.period_key, prior_period.period_key],
                methodology_notes=(
                    f"Delta NWC = NWC_current ({curr_nwc.value}) - NWC_prior ({prior_nwc.value}) = {delta_val}. "
                    f"{'Cash investment/drag' if delta_val > 0 else 'Cash release'}."
                ),
            ),
        )
