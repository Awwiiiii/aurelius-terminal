"""
tests.unit.domain.fundamental.conftest
======================================
Shared deterministic fixtures and factory helpers for fundamental analysis tests.
"""

from datetime import date
from decimal import Decimal

import pytest

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    Filing,
    FinancialConcept,
    FinancialFact,
    FinancialPeriod,
    FinancialStatement,
    FiscalPeriodLabel,
    FiscalPeriodType,
    PeriodType,
    Scale,
    StatementType,
    Unit,
)
from aurelius.domain.fundamental.period_matching import MultiPeriodFactStore


def make_period(
    period_key: str,
    period_type: PeriodType = PeriodType.DURATION,
    fiscal_year: int | None = 2024,
    fiscal_period: FiscalPeriodLabel | None = FiscalPeriodLabel.FY,
    start_date: date | None = None,
) -> FinancialPeriod:
    dt = date.fromisoformat(period_key)
    if period_type == PeriodType.INSTANT:
        return FinancialPeriod(
            period_type=PeriodType.INSTANT,
            instant_date=dt,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            calendar_year=dt.year,
        )
    return FinancialPeriod(
        period_type=PeriodType.DURATION,
        start_date=start_date,
        end_date=dt,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        calendar_year=dt.year,
    )


def make_fact(
    statement_type: StatementType,
    value: Decimal | str,
    period: FinancialPeriod,
    canonical_concept: CanonicalConcept | None = None,
    source_concept: str = "Test Line Item",
    currency: Currency | None = Currency.USD,
    unit: Unit = Unit.CURRENCY,
    fact_id: str | None = None,
) -> FinancialFact:
    dec_val = Decimal(str(value))
    concept = FinancialConcept(
        source_concept=source_concept,
        canonical_concept=canonical_concept,
        statement_type=statement_type,
        taxonomy="test_taxonomy",
    )
    fid = (
        fact_id
        or f"fact_{statement_type.value}_{source_concept.replace(' ', '_')}_{period.period_key}"
    )
    return FinancialFact(
        fact_id=fid,
        company_id="TEST",
        concept=concept,
        value=dec_val,
        unit=unit,
        currency=currency,
        scale=Scale.UNITS,
        period=period,
        filing=Filing(
            filing_id=f"filing_{period.period_key}",
            company_id="TEST",
            report_period_end=period.instant_date
            or period.end_date
            or date(2024, 1, 1),
            source="test",
        ),
    )


def make_statement(
    statement_type: StatementType,
    period: FinancialPeriod,
    facts: list[FinancialFact],
    frequency: FiscalPeriodType = FiscalPeriodType.ANNUAL,
    ticker: str = "TEST",
) -> FinancialStatement:
    return FinancialStatement(
        statement_id=f"{ticker}_{statement_type.value}_{period.period_key}",
        company_id=ticker,
        statement_type=statement_type,
        frequency=frequency,
        period=period,
        facts=facts,
        currency=Currency.USD,
    )


@pytest.fixture
def empty_fact_store() -> MultiPeriodFactStore:
    return MultiPeriodFactStore([])
