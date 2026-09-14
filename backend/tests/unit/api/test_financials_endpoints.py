"""
tests.unit.api.test_financials_endpoints
=========================================
Unit tests for financial statement REST API endpoints.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from aurelius.api.main import app
from aurelius.domain.entities.enums import AssetType, Currency
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialConcept,
    FinancialFact,
    FinancialPeriod,
    FinancialStatement,
    PeriodType,
    Scale,
    StatementType,
    Unit,
)
from aurelius.domain.entities.security import Security
from aurelius.providers.base import MarketDataProvider
from aurelius.services.financial_statement_service import (
    FinancialStatementService,
    get_financial_statement_service,
)


@pytest.fixture
def mock_statement_service() -> AsyncMock:
    provider = AsyncMock(spec=MarketDataProvider)
    provider.name = "mock_provider"
    service = FinancialStatementService(provider=provider)
    return service


def test_get_financial_statements_endpoint():
    p = FinancialPeriod(period_type=PeriodType.DURATION, end_date=date(2024, 9, 30))
    fact = FinancialFact(
        fact_id="f1",
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
        period=p,
    )
    stmt = FinancialStatement(
        statement_id="s1",
        company_id="AAPL",
        statement_type=StatementType.INCOME_STATEMENT,
        period=p,
        facts=[fact],
        currency=Currency.USD,
    )

    mock_service = AsyncMock()
    mock_service.get_statements.return_value = [stmt]

    app.dependency_overrides[get_financial_statement_service] = lambda: mock_service

    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/market/financials/AAPL/statements?statement_type=INCOME_STATEMENT&frequency=ANNUAL"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["company_id"] == "AAPL"
        assert len(data[0]["facts"]) == 1
        assert data[0]["facts"][0]["concept_name"] == "Total Revenue"
        assert data[0]["facts"][0]["canonical_concept"] == "REVENUE"
        # Verify exact numeric value
        assert Decimal(str(data[0]["facts"][0]["value"])) == Decimal("416161000000")
    finally:
        app.dependency_overrides.clear()


def test_get_financial_matrix_endpoint():
    mock_provider = AsyncMock(spec=MarketDataProvider)
    mock_provider.name = "mock_provider"

    mock_provider.get_security.return_value = Security(
        ticker="AAPL",
        name="Apple Inc.",
        asset_type=AssetType.EQUITY,
        currency=Currency.USD,
    )

    p = FinancialPeriod(period_type=PeriodType.DURATION, end_date=date(2024, 9, 30))
    fact = FinancialFact(
        fact_id="f1",
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
        period=p,
    )
    stmt = FinancialStatement(
        statement_id="s1",
        company_id="AAPL",
        statement_type=StatementType.INCOME_STATEMENT,
        period=p,
        facts=[fact],
        currency=Currency.USD,
    )
    mock_provider.get_financial_statements.return_value = [stmt]

    service = FinancialStatementService(provider=mock_provider)
    app.dependency_overrides[get_financial_statement_service] = lambda: service

    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/market/financials/AAPL/matrix?statement_type=INCOME_STATEMENT&frequency=ANNUAL"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["company_id"] == "AAPL"
        assert len(data["periods"]) == 1
        assert len(data["rows"]) >= 1
        rev_row = next(r for r in data["rows"] if r["concept_key"] == "REVENUE")
        assert rev_row["is_canonical"] is True
        assert Decimal(str(rev_row["values_by_period"]["2024-09-30"])) == Decimal(
            "416161000000"
        )
    finally:
        app.dependency_overrides.clear()


def test_non_corporate_instrument_returns_404():
    mock_provider = AsyncMock(spec=MarketDataProvider)
    mock_provider.name = "mock_provider"
    mock_provider.get_security.return_value = Security(
        ticker="SPY",
        name="SPDR S&P 500 ETF Trust",
        asset_type=AssetType.ETF,
        currency=Currency.USD,
    )

    service = FinancialStatementService(provider=mock_provider)
    app.dependency_overrides[get_financial_statement_service] = lambda: service

    try:
        client = TestClient(app)
        response = client.get("/api/v1/market/financials/SPY/matrix")
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "DATA_NOT_FOUND"
        assert "not reported for non-corporate instrument" in data["message"]
    finally:
        app.dependency_overrides.clear()
