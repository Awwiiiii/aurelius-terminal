"""
aurelius.services.operations.ttm_helpers
======================================
Helper utilities for synthesizing TTM statement facts across 4 quarterly periods
using existing M7B.1 TTMEngine principles.
"""

from decimal import Decimal

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialFact,
    FinancialPeriod,
    FinancialStatement,
    FiscalPeriodType,
    StatementType,
)
from aurelius.domain.fundamental.period_matching import (
    MultiPeriodFactStore,
    get_prior_period,
)
from aurelius.domain.fundamental.ttm import TTMEngine, TTMWindow


def find_ttm_window_and_prior(
    sorted_periods: list[FinancialPeriod],
    fiscal_year: int | None = None,
    fiscal_period: str | None = None,
) -> tuple[TTMWindow | None, FinancialPeriod | None]:
    """
    Locate target TTMWindow and the Q(t-4) prior quarter for 1-year Delta NWC.
    Returns (target_window, q_t_minus_4).
    """
    ttm_windows = TTMEngine.find_all_ttm_windows(sorted_periods)
    if not ttm_windows:
        return None, None

    target_window = ttm_windows[-1]
    if fiscal_year is not None:
        matching = [
            w
            for w in ttm_windows
            if w.anchor_quarter.fiscal_year == fiscal_year
            and (
                fiscal_period is None
                or (
                    w.anchor_quarter.fiscal_period
                    and w.anchor_quarter.fiscal_period.value == fiscal_period
                )
            )
        ]
        if matching:
            target_window = matching[-1]

    # Find Q(t-4) as prior consecutive quarter to oldest quarter Q(t-3)
    q_oldest = target_window.quarters[0]
    q_t_minus_4 = get_prior_period(q_oldest, sorted_periods, FiscalPeriodType.QUARTERLY)

    return target_window, q_t_minus_4


def synthesize_ttm_statements(
    window: TTMWindow,
    fact_store: MultiPeriodFactStore,
) -> list[FinancialStatement]:
    """
    Construct synthetic statements for a TTMWindow:
      - Instant facts (Balance Sheet): strictly from anchor quarter Q(t). Never summed.
      - Duration facts (Income Statement & Cash Flow): strictly sum across the 4 consecutive
        quarters [Q(t-3), Q(t-2), Q(t-1), Q(t)].
    """
    synthetic_stmts: list[FinancialStatement] = []
    ttm_period = window.ttm_period
    anchor_q = window.anchor_quarter

    # 1. Balance Sheet: Instant facts at Q(t)
    bs_facts: list[FinancialFact] = []
    for fact in fact_store._all_facts:
        if (
            fact.period.period_key == anchor_q.period_key
            and fact.concept.statement_type == StatementType.BALANCE_SHEET
        ):
            synth_fact = FinancialFact(
                fact_id=f"TTM_{fact.fact_id}",
                company_id=fact.company_id,
                concept=fact.concept,
                value=fact.value,
                unit=fact.unit,
                period=ttm_period,
                currency=fact.currency,
                scale=fact.scale,
                filing=fact.filing,
                dimensions=dict(fact.dimensions),
                provenance=dict(fact.provenance),
            )
            bs_facts.append(synth_fact)

    if bs_facts:
        bs_curr = bs_facts[0].currency
        company_id = bs_facts[0].company_id
        synthetic_stmts.append(
            FinancialStatement(
                statement_id=f"TTM_BS_{ttm_period.period_key}",
                company_id=company_id,
                statement_type=StatementType.BALANCE_SHEET,
                frequency=FiscalPeriodType.TTM,
                period=ttm_period,
                currency=bs_curr,
                facts=bs_facts,
            )
        )

    # 2. Duration Statements: Income Statement & Cash Flow
    for st_type in (StatementType.INCOME_STATEMENT, StatementType.CASH_FLOW):
        dur_facts: list[FinancialFact] = []

        # A. Aggregate canonical concepts
        seen_concepts: set[CanonicalConcept] = set()
        for fact in fact_store._all_facts:
            if (
                fact.period.period_key == anchor_q.period_key
                and fact.concept.statement_type == st_type
                and fact.concept.canonical_concept is not None
            ):
                seen_concepts.add(fact.concept.canonical_concept)

        for canon in seen_concepts:
            q_facts: list[FinancialFact] = []
            for q in window.quarters:
                f = fact_store.get_canonical_fact(st_type, canon, q.period_key)
                if f is not None:
                    q_facts.append(f)
            if len(q_facts) == 4:
                first_curr = q_facts[0].currency
                if all(f.currency == first_curr for f in q_facts):
                    ttm_val = sum((f.value for f in q_facts), Decimal("0"))
                    dur_facts.append(
                        FinancialFact(
                            fact_id=f"TTM_{q_facts[0].fact_id}",
                            company_id=q_facts[0].company_id,
                            concept=q_facts[0].concept,
                            value=ttm_val,
                            unit=q_facts[0].unit,
                            period=ttm_period,
                            currency=first_curr,
                            scale=q_facts[0].scale,
                            filing=q_facts[-1].filing,
                            dimensions=dict(q_facts[-1].dimensions),
                            provenance=dict(q_facts[-1].provenance),
                        )
                    )

        # B. Aggregate source concepts for lines without canonical concepts
        seen_sources: set[str] = set()
        for fact in fact_store._all_facts:
            if (
                fact.period.period_key == anchor_q.period_key
                and fact.concept.statement_type == st_type
                and fact.concept.canonical_concept is None
            ):
                seen_sources.add(fact.concept.source_concept)

        for src in seen_sources:
            q_facts = []
            for q in window.quarters:
                f = fact_store.get_source_fact(st_type, [src], q.period_key)
                if f is not None:
                    q_facts.append(f)
            if len(q_facts) == 4:
                first_curr = q_facts[0].currency
                if all(f.currency == first_curr for f in q_facts):
                    ttm_val = sum((f.value for f in q_facts), Decimal("0"))
                    dur_facts.append(
                        FinancialFact(
                            fact_id=f"TTM_{q_facts[0].fact_id}",
                            company_id=q_facts[0].company_id,
                            concept=q_facts[0].concept,
                            value=ttm_val,
                            unit=q_facts[0].unit,
                            period=ttm_period,
                            currency=first_curr,
                            scale=q_facts[0].scale,
                            filing=q_facts[-1].filing,
                            dimensions=dict(q_facts[-1].dimensions),
                            provenance=dict(q_facts[-1].provenance),
                        )
                    )

        if dur_facts:
            dur_curr = dur_facts[0].currency
            company_id = dur_facts[0].company_id
            synthetic_stmts.append(
                FinancialStatement(
                    statement_id=f"TTM_{st_type.value}_{ttm_period.period_key}",
                    company_id=company_id,
                    statement_type=st_type,
                    frequency=FiscalPeriodType.TTM,
                    period=ttm_period,
                    currency=dur_curr,
                    facts=dur_facts,
                )
            )

    return synthetic_stmts
