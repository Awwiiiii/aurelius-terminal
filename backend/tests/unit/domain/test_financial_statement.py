"""
tests.unit.domain.test_financial_statement
===========================================
Unit tests for FinancialStatement domain model and FinancialStatementMatrix presentation structure.
"""

from datetime import date
from decimal import Decimal

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialConcept,
    FinancialFact,
    FinancialMatrixRow,
    FinancialPeriod,
    FinancialStatement,
    FinancialStatementMatrix,
    FiscalPeriodType,
    PeriodType,
    Scale,
    StatementType,
    Unit,
)


def test_financial_statement_assembly():
    period = FinancialPeriod(
        period_type=PeriodType.DURATION,
        end_date=date(2024, 9, 30),
    )
    concept = FinancialConcept(
        source_concept="Total Revenue",
        canonical_concept=CanonicalConcept.REVENUE,
        statement_type=StatementType.INCOME_STATEMENT,
    )
    fact = FinancialFact(
        fact_id="fact_1",
        company_id="AAPL",
        concept=concept,
        value=Decimal("391035000000"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        scale=Scale.UNITS,
        period=period,
    )
    stmt = FinancialStatement(
        statement_id="stmt_1",
        company_id="AAPL",
        statement_type=StatementType.INCOME_STATEMENT,
        period=period,
        facts=[fact],
        currency=Currency.USD,
    )
    assert stmt.statement_type == StatementType.INCOME_STATEMENT
    assert len(stmt.facts) == 1
    assert stmt.facts[0].value == Decimal("391035000000")


def test_matrix_presentation_structure_missing_is_none():
    """
    FinancialStatementMatrix is strictly a presentation structure.
    Missing facts in a period are represented as None, strictly NEVER converted to Decimal(0).
    """
    p1 = FinancialPeriod(period_type=PeriodType.DURATION, end_date=date(2023, 9, 30))
    p2 = FinancialPeriod(period_type=PeriodType.DURATION, end_date=date(2024, 9, 30))

    row = FinancialMatrixRow(
        concept_key="REVENUE",
        display_name="Revenue",
        canonical_concept=CanonicalConcept.REVENUE,
        is_canonical=True,
        values_by_period={
            "2023-09-30": Decimal("383285000000"),
            "2024-09-30": None,  # Missing in 2024 period
        },
    )

    matrix = FinancialStatementMatrix(
        company_id="AAPL",
        statement_type=StatementType.INCOME_STATEMENT,
        frequency=FiscalPeriodType.ANNUAL,
        currency=Currency.USD,
        periods=[p1, p2],
        rows=[row],
    )

    assert matrix.rows[0].values_by_period["2023-09-30"] == Decimal("383285000000")
    # Crucial correctness rule: missing != zero
    assert matrix.rows[0].values_by_period["2024-09-30"] is None
    assert matrix.rows[0].values_by_period["2024-09-30"] != Decimal("0")
