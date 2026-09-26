"""
aurelius.domain.fundamental.ttm
===============================
Milestone 7B.1 Period & TTM Engine.

Provides rigorous compatible-quarter sequencing, multi-quarter duration aggregation,
instant fact extraction, and auditable provenance tracking for Trailing Twelve Months (TTM)
fundamental analysis.

Key Invariants:
  - Duration facts are summed across exactly 4 chronologically compatible quarters [Q(t-3), Q(t-2), Q(t-1), Q(t)].
  - Instant facts (Balance Sheet) are NEVER summed across quarters.
  - Missing quarters or missing facts are never fabricated or treated as zero; they surface as UNAVAILABLE.
  - Conflicting facts surface an explicit CONFLICTING_PERIOD_FACTS diagnostic.
  - CapEx sign normalization strictly follows M7A positive economic magnitude convention.
  - TTM FCF = TTM CFO - TTM CapEx magnitude.
  - Decimal arithmetic is preserved end-to-end.
"""

import logging
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialFact,
    FinancialPeriod,
    FiscalPeriodLabel,
    FiscalPeriodType,
    PeriodType,
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
    sort_periods_chronologically,
)

logger = logging.getLogger(__name__)


def create_ttm_period(quarters: list[FinancialPeriod]) -> FinancialPeriod:
    """
    Construct a canonical FinancialPeriod representing a TTM window from 4 compatible quarters.

    Temporal boundaries:
      - start_date: start_date of the oldest quarter (Q(t-3)) if available, else None.
      - end_date: end_date of the latest anchor quarter (Q(t)).
      - fiscal_year: fiscal_year of the anchor quarter (Q(t)).
      - fiscal_period: FiscalPeriodLabel.TTM.
      - calendar_year: calendar_year of anchor quarter or anchor quarter end date year.
      - period_type: PeriodType.DURATION.
    """
    if len(quarters) != 4:
        raise ValueError(
            f"create_ttm_period requires exactly 4 quarters, got {len(quarters)}"
        )

    q_oldest = quarters[0]
    q_anchor = quarters[3]

    start_date = q_oldest.start_date
    end_date = q_anchor.end_date
    if end_date is None:
        raise ValueError("Anchor quarter must have a valid end_date.")

    if start_date is not None and start_date > end_date:
        raise ValueError(
            f"TTM start_date ({start_date}) cannot be after anchor end_date ({end_date})."
        )

    calendar_year = q_anchor.calendar_year or (end_date.year if end_date else None)

    return FinancialPeriod(
        period_type=PeriodType.DURATION,
        start_date=start_date,
        end_date=end_date,
        fiscal_year=q_anchor.fiscal_year,
        fiscal_period=FiscalPeriodLabel.TTM,
        is_period_label_source_reported=False,
        calendar_year=calendar_year,
    )


class TTMWindow(BaseModel):
    """
    Represents an auditable, verified sequence of 4 compatible quarters forming a TTM window.
    Quarters are ordered strictly chronologically: [Q(t-3), Q(t-2), Q(t-1), Q(t)].
    """

    model_config = ConfigDict(frozen=True)

    anchor_quarter: FinancialPeriod = Field(
        ..., description="The latest quarter Q(t) defining this TTM cutoff."
    )
    quarters: list[FinancialPeriod] = Field(
        ...,
        description="Exactly four chronologically compatible quarters [Q(t-3), Q(t-2), Q(t-1), Q(t)].",
    )
    ttm_period: FinancialPeriod = Field(
        ...,
        description="Synthesized canonical FinancialPeriod representing this TTM duration.",
    )


class TTMEngine:
    """
    Core domain engine for quarter sequencing, TTM window resolution, duration fact
    aggregation, instant fact selection, and provenance construction.
    """

    METHODOLOGY_VERSION = "1.0.0"
    METHODOLOGY_TAG = "TTM_4_QUARTERS"

    @classmethod
    def resolve_ttm_window(
        cls,
        anchor_quarter: FinancialPeriod,
        all_periods: list[FinancialPeriod],
    ) -> tuple[TTMWindow | None, MetricDiagnostic | None]:
        """
        Verify and resolve the 4 compatible quarters [Q(t-3), Q(t-2), Q(t-1), Q(t)]
        ending at anchor_quarter.

        Strict requirements:
          - quarters must be chronologically compatible.
          - respect fiscal-year boundaries.
          - do not assume calendar quarters.
          - do not use fuzzy date tolerance.
          - missing quarters or gaps return an explicit diagnostic.
        """
        # Deduplicate periods by period_key while preserving order
        seen_keys: set[str] = set()
        deduped_periods: list[FinancialPeriod] = []
        for p in all_periods:
            if p.period_key not in seen_keys:
                seen_keys.add(p.period_key)
                deduped_periods.append(p)

        sorted_periods = sort_periods_chronologically(deduped_periods)

        # Anchor quarter must have authoritative fiscal metadata
        if anchor_quarter.fiscal_year is None or anchor_quarter.fiscal_period is None:
            return None, MetricDiagnostic(
                code=DiagnosticCode.INCOMPATIBLE_TTM_QUARTERS,
                message="Anchor quarter lacks authoritative fiscal year or fiscal period metadata.",
                details={"anchor_period": anchor_quarter.period_key},
            )

        if anchor_quarter.fiscal_period in (
            FiscalPeriodLabel.FY,
            FiscalPeriodLabel.TTM,
        ):
            return None, MetricDiagnostic(
                code=DiagnosticCode.INCOMPATIBLE_TTM_QUARTERS,
                message=f"Anchor period label '{anchor_quarter.fiscal_period.value}' is not a quarterly period.",
                details={"anchor_period": anchor_quarter.period_key},
            )

        q_t = anchor_quarter
        # Find Q(t-1)
        q_t_minus_1 = get_prior_period(q_t, sorted_periods, FiscalPeriodType.QUARTERLY)
        if q_t_minus_1 is None:
            return None, MetricDiagnostic(
                code=DiagnosticCode.INSUFFICIENT_PERIODS_FOR_TTM,
                message="Preceding quarter Q(t-1) is missing or incompatible.",
                details={"anchor_period": q_t.period_key},
            )

        # Find Q(t-2)
        q_t_minus_2 = get_prior_period(
            q_t_minus_1, sorted_periods, FiscalPeriodType.QUARTERLY
        )
        if q_t_minus_2 is None:
            return None, MetricDiagnostic(
                code=DiagnosticCode.INSUFFICIENT_PERIODS_FOR_TTM,
                message="Preceding quarter Q(t-2) is missing or incompatible.",
                details={"anchor_period": q_t.period_key},
            )

        # Find Q(t-3)
        q_t_minus_3 = get_prior_period(
            q_t_minus_2, sorted_periods, FiscalPeriodType.QUARTERLY
        )
        if q_t_minus_3 is None:
            return None, MetricDiagnostic(
                code=DiagnosticCode.INSUFFICIENT_PERIODS_FOR_TTM,
                message="Preceding quarter Q(t-3) is missing or incompatible.",
                details={"anchor_period": q_t.period_key},
            )

        quarters = [q_t_minus_3, q_t_minus_2, q_t_minus_1, q_t]

        # Verify strict chronological progression of end dates
        for i in range(len(quarters) - 1):
            if (
                quarters[i].end_date is None
                or quarters[i + 1].end_date is None
                or quarters[i].end_date >= quarters[i + 1].end_date
            ):
                return None, MetricDiagnostic(
                    code=DiagnosticCode.INCOMPATIBLE_TTM_QUARTERS,
                    message="Quarter sequence violates strict chronological end date ordering.",
                    details={
                        "period_i": quarters[i].period_key,
                        "period_next": quarters[i + 1].period_key,
                    },
                )

        try:
            ttm_period = create_ttm_period(quarters)
        except Exception as e:
            return None, MetricDiagnostic(
                code=DiagnosticCode.INCOMPATIBLE_TTM_QUARTERS,
                message=f"Failed to construct TTM period: {e}",
                details={"anchor_period": q_t.period_key},
            )

        return TTMWindow(
            anchor_quarter=q_t,
            quarters=quarters,
            ttm_period=ttm_period,
        ), None

    @classmethod
    def find_all_ttm_windows(
        cls,
        all_periods: list[FinancialPeriod],
    ) -> list[TTMWindow]:
        """
        Scan a list of financial periods and return all valid TTMWindows in chronological order.
        """
        seen_keys: set[str] = set()
        deduped_periods: list[FinancialPeriod] = []
        for p in all_periods:
            if p.period_key not in seen_keys:
                seen_keys.add(p.period_key)
                deduped_periods.append(p)

        sorted_periods = sort_periods_chronologically(deduped_periods)
        windows: list[TTMWindow] = []

        for p in sorted_periods:
            # Only quarterly periods can serve as anchor quarters
            if p.fiscal_period in (
                FiscalPeriodLabel.Q1,
                FiscalPeriodLabel.Q2,
                FiscalPeriodLabel.Q3,
                FiscalPeriodLabel.Q4,
            ):
                window, _ = cls.resolve_ttm_window(p, sorted_periods)
                if window is not None:
                    windows.append(window)

        return windows

    @classmethod
    def aggregate_duration_fact(
        cls,
        window: TTMWindow,
        statement_type: StatementType,
        concept: CanonicalConcept,
        metric_id: FundamentalMetricId,
        category: MetricCategory,
        fact_store: MultiPeriodFactStore,
        formula_id: str,
    ) -> MetricResult:
        """
        Aggregate a duration fact across the four compatible quarters of a TTMWindow.
        Strict Rules:
          - Rejects INSTANT facts (Balance Sheet) with ValueError.
          - Retrieves facts using get_canonical_fact_checked to identify conflicting facts.
          - Never fabricates missing quarters or treats missing as zero.
          - Returns UNAVAILABLE if any of the four quarters is missing or conflicting.
          - Verifies currency consistency across all 4 quarters.
          - Uses Decimal addition exclusively.
          - Preserves full provenance referencing all 4 source facts.
        """
        if statement_type == StatementType.BALANCE_SHEET:
            raise ValueError(
                f"Cannot aggregate instant facts from {statement_type} in TTMEngine. "
                "Balance sheet facts must use resolve_latest_instant_fact or resolve_instant_pair."
            )

        ttm_period = window.ttm_period
        source_facts: list[FinancialFact] = []
        diagnostics: list[MetricDiagnostic] = []

        for q in window.quarters:
            fact, diag = fact_store.get_canonical_fact_checked(
                statement_type, concept, q.period_key
            )
            if diag is not None:
                diagnostics.append(diag)
            if fact is None:
                diagnostics.append(
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing fact for {concept.value} in quarter {q.period_key}.",
                        details={"quarter": q.period_key, "concept": concept.value},
                    )
                )
            else:
                source_facts.append(fact)

        if len(source_facts) < 4:
            return MetricResult(
                metric_id=metric_id,
                category=category,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=ttm_period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id=formula_id,
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[f.fact_id for f in source_facts],
                    source_concepts=[concept.value],
                    source_periods=[q.period_key for q in window.quarters],
                    methodology_notes=f"{cls.METHODOLOGY_TAG}: Incomplete quarters for duration aggregation.",
                ),
                is_derived=True,
            )

        # Check currency consistency
        first_currency = source_facts[0].currency
        for f in source_facts[1:]:
            if f.currency != first_currency:
                return MetricResult(
                    metric_id=metric_id,
                    category=category,
                    status=MetricStatus.UNAVAILABLE,
                    value=None,
                    unit=Unit.CURRENCY,
                    currency=None,
                    period=ttm_period,
                    diagnostics=[
                        MetricDiagnostic(
                            code=DiagnosticCode.CURRENCY_MISMATCH,
                            message="Currency mismatch across quarterly facts in TTM window.",
                            details={
                                "fact_0_currency": str(first_currency),
                                "mismatch_fact_currency": str(f.currency),
                                "fact_id": f.fact_id,
                            },
                        )
                    ],
                    provenance=MetricProvenance(
                        formula_id=formula_id,
                        methodology_version=cls.METHODOLOGY_VERSION,
                        source_fact_ids=[f.fact_id for f in source_facts],
                        source_concepts=[concept.value],
                        source_periods=[q.period_key for q in window.quarters],
                        methodology_notes=f"{cls.METHODOLOGY_TAG}: Currency mismatch across quarters.",
                    ),
                    is_derived=True,
                )

        # Decimal summation
        ttm_val = sum((f.value for f in source_facts), Decimal("0"))
        provider = (
            source_facts[0].provenance.provider
            if source_facts[0].provenance
            else "yahoo_finance"
        )

        return MetricResult(
            metric_id=metric_id,
            category=category,
            status=MetricStatus.VALID,
            value=ttm_val,
            unit=Unit.CURRENCY,
            currency=first_currency,
            period=ttm_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id=formula_id,
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[f.fact_id for f in source_facts],
                source_concepts=[concept.value],
                source_periods=[q.period_key for q in window.quarters],
                provider=provider,
                methodology_notes=f"{cls.METHODOLOGY_TAG}: Sum of four compatible quarterly facts.",
            ),
            is_derived=True,
        )

    # -------------------------------------------------------------------------
    # Core Duration Fact Calculations
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_ttm_revenue(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM Revenue = Q(t-3) + Q(t-2) + Q(t-1) + Q(t).
        """
        return cls.aggregate_duration_fact(
            window=window,
            statement_type=StatementType.INCOME_STATEMENT,
            concept=CanonicalConcept.REVENUE,
            metric_id=FundamentalMetricId.REVENUE,
            category=MetricCategory.GROWTH,
            fact_store=fact_store,
            formula_id="FORMULA_TTM_REVENUE",
        )

    @classmethod
    def calculate_ttm_gross_profit(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM Gross Profit = Q(t-3) + Q(t-2) + Q(t-1) + Q(t).
        """
        return cls.aggregate_duration_fact(
            window=window,
            statement_type=StatementType.INCOME_STATEMENT,
            concept=CanonicalConcept.GROSS_PROFIT,
            metric_id=FundamentalMetricId.GROSS_PROFIT,
            category=MetricCategory.PROFITABILITY,
            fact_store=fact_store,
            formula_id="FORMULA_TTM_GROSS_PROFIT",
        )

    @classmethod
    def calculate_ttm_operating_income(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM Operating Income = Q(t-3) + Q(t-2) + Q(t-1) + Q(t).
        """
        return cls.aggregate_duration_fact(
            window=window,
            statement_type=StatementType.INCOME_STATEMENT,
            concept=CanonicalConcept.OPERATING_INCOME,
            metric_id=FundamentalMetricId.OPERATING_INCOME,
            category=MetricCategory.PROFITABILITY,
            fact_store=fact_store,
            formula_id="FORMULA_TTM_OPERATING_INCOME",
        )

    @classmethod
    def calculate_ttm_net_income(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM Net Income = Q(t-3) + Q(t-2) + Q(t-1) + Q(t).
        """
        return cls.aggregate_duration_fact(
            window=window,
            statement_type=StatementType.INCOME_STATEMENT,
            concept=CanonicalConcept.NET_INCOME,
            metric_id=FundamentalMetricId.NET_INCOME,
            category=MetricCategory.PROFITABILITY,
            fact_store=fact_store,
            formula_id="FORMULA_TTM_NET_INCOME",
        )

    @classmethod
    def calculate_ttm_cfo(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM Operating Cash Flow = Q(t-3) + Q(t-2) + Q(t-1) + Q(t).
        """
        return cls.aggregate_duration_fact(
            window=window,
            statement_type=StatementType.CASH_FLOW,
            concept=CanonicalConcept.OPERATING_CASH_FLOW,
            metric_id=FundamentalMetricId.OPERATING_CASH_FLOW,
            category=MetricCategory.CASH_FLOW,
            fact_store=fact_store,
            formula_id="FORMULA_TTM_CFO",
        )

    @classmethod
    def calculate_ttm_capex(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM Capital Expenditures = Sum of positive economic magnitudes across 4 compatible quarters.
        Follows M7A canonical convention: magnitude = abs(capex_fact.value).
        """
        ttm_period = window.ttm_period
        source_facts: list[FinancialFact] = []
        diagnostics: list[MetricDiagnostic] = []

        for q in window.quarters:
            fact, diag = fact_store.get_canonical_fact_checked(
                StatementType.CASH_FLOW,
                CanonicalConcept.CAPITAL_EXPENDITURES,
                q.period_key,
            )
            if diag is not None:
                diagnostics.append(diag)
            if fact is None:
                diagnostics.append(
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_REQUIRED_FACT,
                        message=f"Missing Capital Expenditures fact in quarter {q.period_key}.",
                        details={
                            "quarter": q.period_key,
                            "concept": "CAPITAL_EXPENDITURES",
                        },
                    )
                )
            else:
                source_facts.append(fact)

        if len(source_facts) < 4:
            return MetricResult(
                metric_id=FundamentalMetricId.CAPITAL_EXPENDITURES,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=ttm_period,
                diagnostics=diagnostics,
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_CAPEX",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[f.fact_id for f in source_facts],
                    source_concepts=["CAPITAL_EXPENDITURES"],
                    source_periods=[q.period_key for q in window.quarters],
                    methodology_notes=f"{cls.METHODOLOGY_TAG}: Incomplete quarters for TTM CapEx aggregation.",
                ),
                is_derived=True,
            )

        # Check currency consistency
        first_currency = source_facts[0].currency
        for f in source_facts[1:]:
            if f.currency != first_currency:
                return MetricResult(
                    metric_id=FundamentalMetricId.CAPITAL_EXPENDITURES,
                    category=MetricCategory.CASH_FLOW,
                    status=MetricStatus.UNAVAILABLE,
                    value=None,
                    unit=Unit.CURRENCY,
                    currency=None,
                    period=ttm_period,
                    diagnostics=[
                        MetricDiagnostic(
                            code=DiagnosticCode.CURRENCY_MISMATCH,
                            message="Currency mismatch across quarterly CapEx facts.",
                            details={
                                "fact_0_currency": str(first_currency),
                                "mismatch_fact_currency": str(f.currency),
                            },
                        )
                    ],
                    provenance=MetricProvenance(
                        formula_id="FORMULA_TTM_CAPEX",
                        methodology_version=cls.METHODOLOGY_VERSION,
                        source_fact_ids=[f.fact_id for f in source_facts],
                        source_concepts=["CAPITAL_EXPENDITURES"],
                        source_periods=[q.period_key for q in window.quarters],
                        methodology_notes=f"{cls.METHODOLOGY_TAG}: Currency mismatch across quarters.",
                    ),
                    is_derived=True,
                )

        # Sum of positive economic magnitudes abs(value)
        ttm_capex = sum((abs(f.value) for f in source_facts), Decimal("0"))
        provider = (
            source_facts[0].provenance.provider
            if source_facts[0].provenance
            else "yahoo_finance"
        )

        return MetricResult(
            metric_id=FundamentalMetricId.CAPITAL_EXPENDITURES,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=ttm_capex,
            unit=Unit.CURRENCY,
            currency=first_currency,
            period=ttm_period,
            diagnostics=diagnostics,
            provenance=MetricProvenance(
                formula_id="FORMULA_TTM_CAPEX",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[f.fact_id for f in source_facts],
                source_concepts=["CAPITAL_EXPENDITURES"],
                source_periods=[q.period_key for q in window.quarters],
                provider=provider,
                methodology_notes=(
                    f"{cls.METHODOLOGY_TAG}: Sum of four quarterly positive CapEx economic magnitudes abs(val)."
                ),
            ),
            is_derived=True,
        )

    @classmethod
    def calculate_ttm_fcf(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM Free Cash Flow = TTM CFO - TTM CapEx magnitude.
        Strictly requires both TTM CFO and TTM CapEx to be VALID.
        """
        ttm_period = window.ttm_period
        cfo_res = cls.calculate_ttm_cfo(window, fact_store)
        capex_res = cls.calculate_ttm_capex(window, fact_store)

        if (
            cfo_res.status != MetricStatus.VALID
            or capex_res.status != MetricStatus.VALID
        ):
            combined_diags = [*cfo_res.diagnostics, *capex_res.diagnostics]
            combined_fact_ids = [
                *cfo_res.provenance.source_fact_ids,
                *capex_res.provenance.source_fact_ids,
            ]
            return MetricResult(
                metric_id=FundamentalMetricId.FREE_CASH_FLOW,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=ttm_period,
                diagnostics=combined_diags,
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_FCF",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=combined_fact_ids,
                    source_concepts=["OPERATING_CASH_FLOW", "CAPITAL_EXPENDITURES"],
                    source_periods=[q.period_key for q in window.quarters],
                    methodology_notes=f"{cls.METHODOLOGY_TAG}: Requires both valid TTM CFO and valid TTM CapEx.",
                ),
                is_derived=True,
            )

        if cfo_res.currency != capex_res.currency:
            return MetricResult(
                metric_id=FundamentalMetricId.FREE_CASH_FLOW,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.CURRENCY,
                currency=None,
                period=ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.CURRENCY_MISMATCH,
                        message="Currency mismatch between TTM CFO and TTM CapEx.",
                        details={
                            "cfo_currency": str(cfo_res.currency),
                            "capex_currency": str(capex_res.currency),
                        },
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_FCF",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *cfo_res.provenance.source_fact_ids,
                        *capex_res.provenance.source_fact_ids,
                    ],
                    source_concepts=["OPERATING_CASH_FLOW", "CAPITAL_EXPENDITURES"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        fcf_value = cfo_res.value - capex_res.value  # type: ignore[operator]

        return MetricResult(
            metric_id=FundamentalMetricId.FREE_CASH_FLOW,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=fcf_value,
            unit=Unit.CURRENCY,
            currency=cfo_res.currency,
            period=ttm_period,
            diagnostics=[*cfo_res.diagnostics, *capex_res.diagnostics],
            provenance=MetricProvenance(
                formula_id="FORMULA_TTM_FCF",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[
                    *cfo_res.provenance.source_fact_ids,
                    *capex_res.provenance.source_fact_ids,
                ],
                source_concepts=["OPERATING_CASH_FLOW", "CAPITAL_EXPENDITURES"],
                source_periods=[q.period_key for q in window.quarters],
                provider=cfo_res.provenance.provider,
                methodology_notes=(
                    f"{cls.METHODOLOGY_TAG}: TTM Free Cash Flow = TTM Operating Cash Flow - TTM CapEx magnitude."
                ),
            ),
            is_derived=True,
        )

    # -------------------------------------------------------------------------
    # TTM Ratio and Margin Calculations
    # -------------------------------------------------------------------------

    @classmethod
    def calculate_ttm_gross_margin(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM Gross Margin = TTM Gross Profit / TTM Revenue.
        """
        ttm_period = window.ttm_period
        gp = cls.calculate_ttm_gross_profit(window, fact_store)
        rev = cls.calculate_ttm_revenue(window, fact_store)

        if gp.status != MetricStatus.VALID or rev.status != MetricStatus.VALID:
            return MetricResult(
                metric_id=FundamentalMetricId.GROSS_PROFIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                period=ttm_period,
                diagnostics=[*gp.diagnostics, *rev.diagnostics],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_GROSS_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *gp.provenance.source_fact_ids,
                        *rev.provenance.source_fact_ids,
                    ],
                    source_concepts=["GROSS_PROFIT", "REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        if rev.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.GROSS_PROFIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                period=ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="TTM Revenue is zero; gross margin is mathematically undefined.",
                        details={"denominator": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_GROSS_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *gp.provenance.source_fact_ids,
                        *rev.provenance.source_fact_ids,
                    ],
                    source_concepts=["GROSS_PROFIT", "REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        val = gp.value / rev.value  # type: ignore[operator]
        return MetricResult(
            metric_id=FundamentalMetricId.GROSS_PROFIT_MARGIN,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=val,
            unit=Unit.PERCENT,
            period=ttm_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_TTM_GROSS_MARGIN",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[
                    *gp.provenance.source_fact_ids,
                    *rev.provenance.source_fact_ids,
                ],
                source_concepts=["GROSS_PROFIT", "REVENUE"],
                source_periods=[q.period_key for q in window.quarters],
                provider=rev.provenance.provider,
                methodology_notes=f"{cls.METHODOLOGY_TAG}: TTM Gross Profit / TTM Revenue.",
            ),
            is_derived=True,
        )

    @classmethod
    def calculate_ttm_operating_margin(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM Operating Margin = TTM Operating Income / TTM Revenue.
        """
        ttm_period = window.ttm_period
        op = cls.calculate_ttm_operating_income(window, fact_store)
        rev = cls.calculate_ttm_revenue(window, fact_store)

        if op.status != MetricStatus.VALID or rev.status != MetricStatus.VALID:
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                period=ttm_period,
                diagnostics=[*op.diagnostics, *rev.diagnostics],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_OPERATING_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *op.provenance.source_fact_ids,
                        *rev.provenance.source_fact_ids,
                    ],
                    source_concepts=["OPERATING_INCOME", "REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        if rev.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.OPERATING_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                period=ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="TTM Revenue is zero; operating margin is mathematically undefined.",
                        details={"denominator": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_OPERATING_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *op.provenance.source_fact_ids,
                        *rev.provenance.source_fact_ids,
                    ],
                    source_concepts=["OPERATING_INCOME", "REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        val = op.value / rev.value  # type: ignore[operator]
        return MetricResult(
            metric_id=FundamentalMetricId.OPERATING_MARGIN,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=val,
            unit=Unit.PERCENT,
            period=ttm_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_TTM_OPERATING_MARGIN",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[
                    *op.provenance.source_fact_ids,
                    *rev.provenance.source_fact_ids,
                ],
                source_concepts=["OPERATING_INCOME", "REVENUE"],
                source_periods=[q.period_key for q in window.quarters],
                provider=rev.provenance.provider,
                methodology_notes=f"{cls.METHODOLOGY_TAG}: TTM Operating Income / TTM Revenue.",
            ),
            is_derived=True,
        )

    @classmethod
    def calculate_ttm_net_profit_margin(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM Net Profit Margin = TTM Net Income / TTM Revenue.
        """
        ttm_period = window.ttm_period
        ni = cls.calculate_ttm_net_income(window, fact_store)
        rev = cls.calculate_ttm_revenue(window, fact_store)

        if ni.status != MetricStatus.VALID or rev.status != MetricStatus.VALID:
            return MetricResult(
                metric_id=FundamentalMetricId.NET_PROFIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                period=ttm_period,
                diagnostics=[*ni.diagnostics, *rev.diagnostics],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_NET_PROFIT_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *ni.provenance.source_fact_ids,
                        *rev.provenance.source_fact_ids,
                    ],
                    source_concepts=["NET_INCOME", "REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        if rev.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.NET_PROFIT_MARGIN,
                category=MetricCategory.PROFITABILITY,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                period=ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="TTM Revenue is zero; net profit margin is mathematically undefined.",
                        details={"denominator": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_NET_PROFIT_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *ni.provenance.source_fact_ids,
                        *rev.provenance.source_fact_ids,
                    ],
                    source_concepts=["NET_INCOME", "REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        val = ni.value / rev.value  # type: ignore[operator]
        return MetricResult(
            metric_id=FundamentalMetricId.NET_PROFIT_MARGIN,
            category=MetricCategory.PROFITABILITY,
            status=MetricStatus.VALID,
            value=val,
            unit=Unit.PERCENT,
            period=ttm_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_TTM_NET_PROFIT_MARGIN",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[
                    *ni.provenance.source_fact_ids,
                    *rev.provenance.source_fact_ids,
                ],
                source_concepts=["NET_INCOME", "REVENUE"],
                source_periods=[q.period_key for q in window.quarters],
                provider=rev.provenance.provider,
                methodology_notes=f"{cls.METHODOLOGY_TAG}: TTM Net Income / TTM Revenue.",
            ),
            is_derived=True,
        )

    @classmethod
    def calculate_ttm_fcf_margin(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM FCF Margin = TTM Free Cash Flow / TTM Revenue.
        """
        ttm_period = window.ttm_period
        fcf = cls.calculate_ttm_fcf(window, fact_store)
        rev = cls.calculate_ttm_revenue(window, fact_store)

        if fcf.status != MetricStatus.VALID or rev.status != MetricStatus.VALID:
            return MetricResult(
                metric_id=FundamentalMetricId.FCF_MARGIN,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                period=ttm_period,
                diagnostics=[*fcf.diagnostics, *rev.diagnostics],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_FCF_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *fcf.provenance.source_fact_ids,
                        *rev.provenance.source_fact_ids,
                    ],
                    source_concepts=["FREE_CASH_FLOW", "REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        if rev.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.FCF_MARGIN,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.PERCENT,
                period=ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="TTM Revenue is zero; FCF margin is mathematically undefined.",
                        details={"denominator": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_FCF_MARGIN",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *fcf.provenance.source_fact_ids,
                        *rev.provenance.source_fact_ids,
                    ],
                    source_concepts=["FREE_CASH_FLOW", "REVENUE"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        val = fcf.value / rev.value  # type: ignore[operator]
        return MetricResult(
            metric_id=FundamentalMetricId.FCF_MARGIN,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=val,
            unit=Unit.PERCENT,
            period=ttm_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_TTM_FCF_MARGIN",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[
                    *fcf.provenance.source_fact_ids,
                    *rev.provenance.source_fact_ids,
                ],
                source_concepts=["FREE_CASH_FLOW", "REVENUE"],
                source_periods=[q.period_key for q in window.quarters],
                provider=rev.provenance.provider,
                methodology_notes=f"{cls.METHODOLOGY_TAG}: TTM Free Cash Flow / TTM Revenue.",
            ),
            is_derived=True,
        )

    @classmethod
    def calculate_ttm_fcf_conversion(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM FCF Conversion = TTM Free Cash Flow / TTM Net Income.
        """
        ttm_period = window.ttm_period
        fcf = cls.calculate_ttm_fcf(window, fact_store)
        ni = cls.calculate_ttm_net_income(window, fact_store)

        if fcf.status != MetricStatus.VALID or ni.status != MetricStatus.VALID:
            return MetricResult(
                metric_id=FundamentalMetricId.FCF_CONVERSION,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                period=ttm_period,
                diagnostics=[*fcf.diagnostics, *ni.diagnostics],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_FCF_CONVERSION",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *fcf.provenance.source_fact_ids,
                        *ni.provenance.source_fact_ids,
                    ],
                    source_concepts=["FREE_CASH_FLOW", "NET_INCOME"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        if ni.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.FCF_CONVERSION,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                period=ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="TTM Net Income is zero; FCF conversion ratio is mathematically undefined.",
                        details={"denominator": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_FCF_CONVERSION",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *fcf.provenance.source_fact_ids,
                        *ni.provenance.source_fact_ids,
                    ],
                    source_concepts=["FREE_CASH_FLOW", "NET_INCOME"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        val = fcf.value / ni.value  # type: ignore[operator]
        return MetricResult(
            metric_id=FundamentalMetricId.FCF_CONVERSION,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=val,
            unit=Unit.RATIO,
            period=ttm_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_TTM_FCF_CONVERSION",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[
                    *fcf.provenance.source_fact_ids,
                    *ni.provenance.source_fact_ids,
                ],
                source_concepts=["FREE_CASH_FLOW", "NET_INCOME"],
                source_periods=[q.period_key for q in window.quarters],
                provider=ni.provenance.provider,
                methodology_notes=f"{cls.METHODOLOGY_TAG}: TTM Free Cash Flow / TTM Net Income.",
            ),
            is_derived=True,
        )

    @classmethod
    def calculate_ttm_cfo_to_net_income(
        cls, window: TTMWindow, fact_store: MultiPeriodFactStore
    ) -> MetricResult:
        """
        TTM CFO to Net Income = TTM CFO / TTM Net Income.
        """
        ttm_period = window.ttm_period
        cfo = cls.calculate_ttm_cfo(window, fact_store)
        ni = cls.calculate_ttm_net_income(window, fact_store)

        if cfo.status != MetricStatus.VALID or ni.status != MetricStatus.VALID:
            return MetricResult(
                metric_id=FundamentalMetricId.CFO_TO_NET_INCOME,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                period=ttm_period,
                diagnostics=[*cfo.diagnostics, *ni.diagnostics],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_CFO_TO_NET_INCOME",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *cfo.provenance.source_fact_ids,
                        *ni.provenance.source_fact_ids,
                    ],
                    source_concepts=["OPERATING_CASH_FLOW", "NET_INCOME"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        if ni.value == Decimal("0"):
            return MetricResult(
                metric_id=FundamentalMetricId.CFO_TO_NET_INCOME,
                category=MetricCategory.CASH_FLOW,
                status=MetricStatus.UNAVAILABLE,
                value=None,
                unit=Unit.RATIO,
                period=ttm_period,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.ZERO_DIVISION,
                        message="TTM Net Income is zero; CFO to Net Income ratio is mathematically undefined.",
                        details={"denominator": "0"},
                    )
                ],
                provenance=MetricProvenance(
                    formula_id="FORMULA_TTM_CFO_TO_NET_INCOME",
                    methodology_version=cls.METHODOLOGY_VERSION,
                    source_fact_ids=[
                        *cfo.provenance.source_fact_ids,
                        *ni.provenance.source_fact_ids,
                    ],
                    source_concepts=["OPERATING_CASH_FLOW", "NET_INCOME"],
                    source_periods=[q.period_key for q in window.quarters],
                ),
                is_derived=True,
            )

        val = cfo.value / ni.value  # type: ignore[operator]
        return MetricResult(
            metric_id=FundamentalMetricId.CFO_TO_NET_INCOME,
            category=MetricCategory.CASH_FLOW,
            status=MetricStatus.VALID,
            value=val,
            unit=Unit.RATIO,
            period=ttm_period,
            diagnostics=[],
            provenance=MetricProvenance(
                formula_id="FORMULA_TTM_CFO_TO_NET_INCOME",
                methodology_version=cls.METHODOLOGY_VERSION,
                source_fact_ids=[
                    *cfo.provenance.source_fact_ids,
                    *ni.provenance.source_fact_ids,
                ],
                source_concepts=["OPERATING_CASH_FLOW", "NET_INCOME"],
                source_periods=[q.period_key for q in window.quarters],
                provider=ni.provenance.provider,
                methodology_notes=f"{cls.METHODOLOGY_TAG}: TTM Operating Cash Flow / TTM Net Income.",
            ),
            is_derived=True,
        )

    # -------------------------------------------------------------------------
    # Instant Fact Helpers (Balance Sheet)
    # -------------------------------------------------------------------------

    @classmethod
    def resolve_latest_instant_fact(
        cls,
        window: TTMWindow,
        statement_type: StatementType,
        concept: CanonicalConcept,
        fact_store: MultiPeriodFactStore,
    ) -> tuple[FinancialFact | None, MetricDiagnostic | None]:
        """
        Retrieve the latest quarter-end instant fact measured at Q(t).
        Never aggregates or sums across quarters.
        """
        anchor_q = window.anchor_quarter
        return fact_store.get_canonical_fact_checked(
            statement_type, concept, anchor_q.period_key
        )

    @classmethod
    def resolve_instant_pair(
        cls,
        window: TTMWindow,
        statement_type: StatementType,
        concept: CanonicalConcept,
        fact_store: MultiPeriodFactStore,
        all_periods: list[FinancialPeriod] | None = None,
    ) -> tuple[FinancialFact | None, FinancialFact | None, list[MetricDiagnostic]]:
        """
        Retrieve the ending instant fact (at Q(t)) and the beginning instant fact (at the start
        of Q(t-3), which corresponds to the quarter-end of Q(t-4)).

        Returns (ending_fact, beginning_fact, diagnostics).
        """
        diagnostics: list[MetricDiagnostic] = []

        # Ending fact at Q(t)
        ending_fact, end_diag = cls.resolve_latest_instant_fact(
            window, statement_type, concept, fact_store
        )
        if end_diag is not None:
            diagnostics.append(end_diag)

        beginning_fact: FinancialFact | None = None
        if all_periods is not None:
            # Look for Q(t-4) as prior consecutive quarter to Q(t-3)
            q_oldest = window.quarters[0]
            q_prior = get_prior_period(
                q_oldest, all_periods, FiscalPeriodType.QUARTERLY
            )
            if q_prior is not None:
                beginning_fact, beg_diag = fact_store.get_canonical_fact_checked(
                    statement_type, concept, q_prior.period_key
                )
                if beg_diag is not None:
                    diagnostics.append(beg_diag)
            else:
                diagnostics.append(
                    MetricDiagnostic(
                        code=DiagnosticCode.MISSING_PRIOR_PERIOD,
                        message="Beginning period Q(t-4) for 2-point TTM average is unavailable.",
                        details={"oldest_quarter": q_oldest.period_key},
                    )
                )

        return ending_fact, beginning_fact, diagnostics
