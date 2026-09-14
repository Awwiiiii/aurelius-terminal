"""
tests.unit.services.test_financial_statement_service
===================================================
Unit tests for FinancialStatementService orchestration and matrix assembly.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from aurelius.domain.entities.enums import AssetType, Currency
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialConcept,
    FinancialFact,
    FinancialPeriod,
    FinancialStatement,
    FiscalPeriodType,
    PeriodType,
    Scale,
    StatementType,
    Unit,
)
from aurelius.domain.entities.security import Security
from aurelius.domain.errors import DataNotFoundError, InvalidTickerError
from aurelius.providers.base import MarketDataProvider
from aurelius.services.financial_statement_service import FinancialStatementService


@pytest.fixture
def mock_provider() -> AsyncMock:
    provider = AsyncMock(spec=MarketDataProvider)
    provider.name = "mock_provider"
    return provider


@pytest.mark.asyncio
async def test_non_corporate_asset_rejected(mock_provider):
    """
    Non-corporate instruments (such as ETFs or Indices) do not disclose financial
    statements and must raise DataNotFoundError.
    """
    mock_provider.get_security.return_value = Security(
        ticker="SPY",
        name="SPDR S&P 500 ETF Trust",
        asset_type=AssetType.ETF,
        currency=Currency.USD,
    )

    service = FinancialStatementService(provider=mock_provider)

    with pytest.raises(
        DataNotFoundError, match="not reported for non-corporate instrument"
    ):
        await service.get_statements("SPY", StatementType.INCOME_STATEMENT)


@pytest.mark.asyncio
async def test_invalid_ticker_rejected(mock_provider):
    service = FinancialStatementService(provider=mock_provider)
    with pytest.raises(InvalidTickerError):
        await service.get_statements("INVALID!!", StatementType.INCOME_STATEMENT)


@pytest.mark.asyncio
async def test_statement_matrix_canonical_ordering_and_missing_none(mock_provider):
    """
    Tests that get_statement_matrix sorts canonical line items in logical financial order,
    and missing observations evaluate to None (never 0).
    """
    mock_provider.get_security.return_value = Security(
        ticker="AAPL",
        name="Apple Inc.",
        asset_type=AssetType.EQUITY,
        currency=Currency.USD,
    )

    p1 = FinancialPeriod(period_type=PeriodType.DURATION, end_date=date(2023, 9, 30))
    p2 = FinancialPeriod(period_type=PeriodType.DURATION, end_date=date(2024, 9, 30))

    fact_rev_2023 = FinancialFact(
        fact_id="f1",
        company_id="AAPL",
        concept=FinancialConcept(
            source_concept="Total Revenue",
            canonical_concept=CanonicalConcept.REVENUE,
            statement_type=StatementType.INCOME_STATEMENT,
        ),
        value=Decimal("383285000000"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        scale=Scale.UNITS,
        period=p1,
    )
    fact_rev_2024 = FinancialFact(
        fact_id="f2",
        company_id="AAPL",
        concept=FinancialConcept(
            source_concept="Total Revenue",
            canonical_concept=CanonicalConcept.REVENUE,
            statement_type=StatementType.INCOME_STATEMENT,
        ),
        value=Decimal("416161000000"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        scale=Scale.UNITS,
        period=p2,
    )
    # R&D only in 2024
    fact_rd_2024 = FinancialFact(
        fact_id="f3",
        company_id="AAPL",
        concept=FinancialConcept(
            source_concept="Research And Development",
            canonical_concept=CanonicalConcept.RESEARCH_AND_DEVELOPMENT,
            statement_type=StatementType.INCOME_STATEMENT,
        ),
        value=Decimal("31000000000"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        scale=Scale.UNITS,
        period=p2,
    )

    stmt_2023 = FinancialStatement(
        statement_id="s1",
        company_id="AAPL",
        statement_type=StatementType.INCOME_STATEMENT,
        period=p1,
        facts=[fact_rev_2023],
        currency=Currency.USD,
    )
    stmt_2024 = FinancialStatement(
        statement_id="s2",
        company_id="AAPL",
        statement_type=StatementType.INCOME_STATEMENT,
        period=p2,
        facts=[fact_rev_2024, fact_rd_2024],
        currency=Currency.USD,
    )

    mock_provider.get_financial_statements.return_value = [stmt_2023, stmt_2024]

    service = FinancialStatementService(provider=mock_provider)
    matrix = await service.get_statement_matrix(
        "AAPL", StatementType.INCOME_STATEMENT, FiscalPeriodType.ANNUAL
    )

    assert matrix.company_id == "AAPL"
    assert len(matrix.periods) == 2

    # Revenue is first in canonical order, followed by R&D
    concept_keys = [r.concept_key for r in matrix.rows]
    assert "REVENUE" in concept_keys
    assert "RESEARCH_AND_DEVELOPMENT" in concept_keys
    assert concept_keys.index("REVENUE") < concept_keys.index(
        "RESEARCH_AND_DEVELOPMENT"
    )

    # Check R&D values: 2023 is None (missing), 2024 is Decimal("31000000000")
    rd_row = next(r for r in matrix.rows if r.concept_key == "RESEARCH_AND_DEVELOPMENT")
    assert rd_row.values_by_period["2023-09-30"] is None
    assert rd_row.values_by_period["2024-09-30"] == Decimal("31000000000")
