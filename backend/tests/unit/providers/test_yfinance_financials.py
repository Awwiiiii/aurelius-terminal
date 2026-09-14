"""
tests.unit.providers.test_yfinance_financials
=============================================
Unit tests for YFinanceProvider financial statement extraction and normalization.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FiscalPeriodType,
    PeriodType,
    Scale,
    StatementType,
    Unit,
)
from aurelius.providers.yfinance_provider import YFinanceProvider


@pytest.fixture
def yfinance_provider() -> YFinanceProvider:
    return YFinanceProvider()


@pytest.mark.asyncio
async def test_get_financial_statements_income_statement(yfinance_provider):
    """
    Tests income statement extraction, NaN handling (omitted, not 0), Decimal values,
    and explicit Yahoo Finance provenance.
    """
    # Mock yfinance dataframe with NaNs
    df = pd.DataFrame(
        {
            pd.Timestamp("2024-09-30"): [416161000000.0, 100000000000.0, float("nan")],
            pd.Timestamp("2023-09-30"): [383285000000.0, 95000000000.0, 5000000000.0],
        },
        index=["Total Revenue", "Operating Income", "Normalized EBITDA"],
    )

    mock_ticker = MagicMock()
    mock_ticker.financials = df
    mock_ticker.fast_info.currency = "USD"

    with patch("yfinance.Ticker", return_value=mock_ticker):
        statements = await yfinance_provider.get_financial_statements(
            "AAPL", StatementType.INCOME_STATEMENT, FiscalPeriodType.ANNUAL
        )

    # Sorted chronologically ascending: 2023-09-30, then 2024-09-30
    assert len(statements) == 2

    stmt_2023 = statements[0]
    assert stmt_2023.period.period_type == PeriodType.DURATION
    assert stmt_2023.period.end_date == date(2023, 9, 30)
    assert stmt_2023.filing.source == "yahoo_finance"
    assert stmt_2023.filing.accession_number is None
    assert stmt_2023.filing.filing_date is None
    assert stmt_2023.filing.report_period_end == date(2023, 9, 30)
    assert len(stmt_2023.facts) == 3

    # Check 2024: Normalized EBITDA was NaN, so it MUST NOT be present in facts (Missing != 0)
    stmt_2024 = statements[1]
    assert stmt_2024.period.end_date == date(2024, 9, 30)
    fact_concepts = [f.concept.source_concept for f in stmt_2024.facts]
    assert "Total Revenue" in fact_concepts
    assert "Operating Income" in fact_concepts
    assert "Normalized EBITDA" not in fact_concepts
    assert len(stmt_2024.facts) == 2

    # Verify Decimal values and canonical mapping
    rev_fact = next(
        f for f in stmt_2024.facts if f.concept.source_concept == "Total Revenue"
    )
    assert isinstance(rev_fact.value, Decimal)
    assert rev_fact.value == Decimal("416161000000")
    assert rev_fact.concept.canonical_concept == CanonicalConcept.REVENUE
    assert rev_fact.unit == Unit.CURRENCY
    assert rev_fact.scale == Scale.UNITS


@pytest.mark.asyncio
async def test_get_financial_statements_balance_sheet_instant_period(yfinance_provider):
    """
    Tests balance sheet extraction verifies PeriodType.INSTANT.
    """
    df = pd.DataFrame(
        {
            pd.Timestamp("2024-09-30"): [30000000000.0, 350000000000.0],
        },
        index=["Cash And Cash Equivalents", "Total Assets"],
    )

    mock_ticker = MagicMock()
    mock_ticker.balance_sheet = df
    mock_ticker.fast_info.currency = "USD"

    with patch("yfinance.Ticker", return_value=mock_ticker):
        statements = await yfinance_provider.get_financial_statements(
            "AAPL", StatementType.BALANCE_SHEET, FiscalPeriodType.ANNUAL
        )

    assert len(statements) == 1
    stmt = statements[0]
    assert stmt.period.period_type == PeriodType.INSTANT
    assert stmt.period.instant_date == date(2024, 9, 30)
    assert stmt.period.end_date is None


@pytest.mark.asyncio
async def test_get_financial_statements_empty_dataframe(yfinance_provider):
    """
    Empty dataframe returns empty list cleanly without errors.
    """
    mock_ticker = MagicMock()
    mock_ticker.financials = pd.DataFrame()

    with patch("yfinance.Ticker", return_value=mock_ticker):
        statements = await yfinance_provider.get_financial_statements(
            "AAPL", StatementType.INCOME_STATEMENT, FiscalPeriodType.ANNUAL
        )

    assert statements == []
