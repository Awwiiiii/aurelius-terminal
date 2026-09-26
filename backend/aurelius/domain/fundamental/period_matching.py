"""
aurelius.domain.fundamental.period_matching
===========================================
Deterministic period pairing, MultiPeriodFactStore, and strict two-point
balance sheet averaging infrastructure.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialFact,
    FinancialPeriod,
    FinancialStatement,
    FiscalPeriodLabel,
    FiscalPeriodType,
    StatementType,
)
from aurelius.domain.fundamental.enums import DiagnosticCode
from aurelius.domain.fundamental.models import MetricDiagnostic


def _is_consecutive_annual(candidate: FinancialPeriod, target: FinancialPeriod) -> bool:
    """
    Verify candidate is strictly the preceding consecutive fiscal year.
    Disallows quarterly periods and multi-year gaps.
    """
    if candidate.fiscal_period in (
        FiscalPeriodLabel.Q1,
        FiscalPeriodLabel.Q2,
        FiscalPeriodLabel.Q3,
        FiscalPeriodLabel.Q4,
    ) or target.fiscal_period in (
        FiscalPeriodLabel.Q1,
        FiscalPeriodLabel.Q2,
        FiscalPeriodLabel.Q3,
        FiscalPeriodLabel.Q4,
    ):
        return False

    t_yr = target.fiscal_year or target.calendar_year
    c_yr = candidate.fiscal_year or candidate.calendar_year
    if t_yr is None or c_yr is None:
        return False

    return c_yr == t_yr - 1


def _is_consecutive_quarter(
    candidate: FinancialPeriod, target: FinancialPeriod
) -> bool:
    """
    Verify candidate is strictly the immediately preceding fiscal quarter,
    accounting for year-boundary progression (Q1 year Y -> Q4 year Y-1).
    Disallows annual FY periods and non-consecutive quarter gaps.
    """
    if (
        candidate.fiscal_period == FiscalPeriodLabel.FY
        or target.fiscal_period == FiscalPeriodLabel.FY
    ):
        return False

    if (
        candidate.fiscal_year is None
        or target.fiscal_year is None
        or candidate.fiscal_period is None
        or target.fiscal_period is None
    ):
        return False

    if target.fiscal_period == FiscalPeriodLabel.Q1:
        return (
            candidate.fiscal_year == target.fiscal_year - 1
            and candidate.fiscal_period == FiscalPeriodLabel.Q4
        )
    if target.fiscal_period == FiscalPeriodLabel.Q2:
        return (
            candidate.fiscal_year == target.fiscal_year
            and candidate.fiscal_period == FiscalPeriodLabel.Q1
        )
    if target.fiscal_period == FiscalPeriodLabel.Q3:
        return (
            candidate.fiscal_year == target.fiscal_year
            and candidate.fiscal_period == FiscalPeriodLabel.Q2
        )
    if target.fiscal_period == FiscalPeriodLabel.Q4:
        return (
            candidate.fiscal_year == target.fiscal_year
            and candidate.fiscal_period == FiscalPeriodLabel.Q3
        )
    return False


def get_prior_period(
    target_period: FinancialPeriod,
    all_periods: list[FinancialPeriod],
    frequency: FiscalPeriodType,
) -> FinancialPeriod | None:
    """
    Find the logically preceding consecutive period in a sorted list of periods.
    For ANNUAL: candidate must strictly be the consecutive prior year (target.fiscal_year - 1).
    For QUARTERLY: candidate must strictly be the immediately preceding fiscal quarter.
    Returns None if no consecutive prior period exists or if frequencies mismatch.
    """
    sorted_p = sort_periods_chronologically(all_periods)
    target_key = target_period.period_key

    for i, p in enumerate(sorted_p):
        if p.period_key == target_key:
            if i > 0:
                candidate = sorted_p[i - 1]
                if frequency == FiscalPeriodType.ANNUAL:
                    if _is_consecutive_annual(candidate, target_period):
                        return candidate
                    return None
                if frequency == FiscalPeriodType.QUARTERLY:
                    if _is_consecutive_quarter(candidate, target_period):
                        return candidate
                    return None
            return None
    return None


class MultiPeriodFactStore:
    """
    Indexed in-memory registry of FinancialFact observations across statements and periods.
    Allows O(1) canonical concept lookups and fallback source concept lookups.
    """

    def __init__(self, statements: list[FinancialStatement]) -> None:
        self._canonical_index: dict[
            tuple[StatementType, CanonicalConcept, str], FinancialFact
        ] = {}
        self._source_index: dict[tuple[StatementType, str, str], FinancialFact] = {}
        self._all_facts: list[FinancialFact] = []

        for stmt in statements:
            p_key = stmt.period.period_key
            for fact in stmt.facts:
                self._all_facts.append(fact)
                st_type = fact.concept.statement_type
                if fact.concept.canonical_concept is not None:
                    self._canonical_index[
                        (st_type, fact.concept.canonical_concept, p_key)
                    ] = fact

                norm_source = fact.concept.source_concept.strip().lower()
                self._source_index[(st_type, norm_source, p_key)] = fact

    def get_canonical_fact(
        self,
        statement_type: StatementType,
        concept: CanonicalConcept,
        period_key: str,
    ) -> FinancialFact | None:
        """
        Retrieve a fact by its exact canonical concept taxonomy.
        """
        return self._canonical_index.get((statement_type, concept, period_key))

    def get_source_fact(
        self,
        statement_type: StatementType,
        candidate_source_names: list[str],
        period_key: str,
    ) -> FinancialFact | None:
        """
        Retrieve an unmapped or vendor fact by matching any of the candidate source labels.
        """
        for name in candidate_source_names:
            norm = name.strip().lower()
            fact = self._source_index.get((statement_type, norm, period_key))
            if fact is not None:
                return fact
        return None


def sort_periods_chronologically(
    periods: list[FinancialPeriod],
) -> list[FinancialPeriod]:
    """
    Sort financial periods in ascending chronological order.
    """

    def _sort_key(p: FinancialPeriod) -> tuple[int, int, str]:
        # Sort primarily by fiscal year (or calendar year), then month/day
        yr = p.fiscal_year or p.calendar_year or 0
        cutoff = p.instant_date or p.end_date
        d_str = cutoff.isoformat() if cutoff else ""
        return (yr, cutoff.month if cutoff else 0, d_str)

    return sorted(periods, key=_sort_key)


def calculate_two_point_average(
    concept: CanonicalConcept,
    current_period: FinancialPeriod,
    prior_period: FinancialPeriod | None,
    fact_store: MultiPeriodFactStore,
    allow_point_in_time_fallback: bool = False,
) -> tuple[Decimal | None, MetricDiagnostic | None, bool, list[FinancialFact]]:
    """
    Calculate strict two-point balance sheet average: (ending + beginning) / 2.

    Returns:
      (average_value, diagnostic, used_fallback, list_of_contributing_facts)
    """
    end_fact = fact_store.get_canonical_fact(
        StatementType.BALANCE_SHEET, concept, current_period.period_key
    )
    if end_fact is None:
        return (
            None,
            MetricDiagnostic(
                code=DiagnosticCode.MISSING_REQUIRED_FACT,
                message=f"Required ending balance sheet fact '{concept.value}' is missing.",
                details={"concept": concept.value, "period": current_period.period_key},
            ),
            False,
            [],
        )

    # If prior period is available, attempt to retrieve beginning balance fact
    beg_fact: FinancialFact | None = None
    if prior_period is not None:
        beg_fact = fact_store.get_canonical_fact(
            StatementType.BALANCE_SHEET, concept, prior_period.period_key
        )

    if beg_fact is not None:
        avg_val = (end_fact.value + beg_fact.value) / Decimal("2")
        return (avg_val, None, False, [beg_fact, end_fact])

    # Beginning balance is unavailable
    if not allow_point_in_time_fallback:
        return (
            None,
            MetricDiagnostic(
                code=DiagnosticCode.INSUFFICIENT_PERIODS_FOR_AVERAGE,
                message=(
                    f"Beginning balance sheet value for '{concept.value}' is unavailable. "
                    "Two-point average requires both beginning and ending balances."
                ),
                details={"concept": concept.value, "period": current_period.period_key},
            ),
            False,
            [end_fact],
        )

    # Explicit fallback to point-in-time ending value
    return (
        end_fact.value,
        MetricDiagnostic(
            code=DiagnosticCode.POINT_IN_TIME_DENOMINATOR_FALLBACK,
            message=(
                f"Beginning balance for '{concept.value}' was unavailable; "
                "ending point-in-time value was used under explicit fallback mode."
            ),
            details={"concept": concept.value, "period": current_period.period_key},
        ),
        True,
        [end_fact],
    )
