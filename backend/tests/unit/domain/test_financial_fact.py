"""
tests.unit.domain.test_financial_fact
=====================================
Unit tests for FinancialFact observation entity, Decimal precision, unit/currency/scale
orthogonality, provenance, and data quality constraints.
"""

from datetime import date
from decimal import Decimal

import pytest

from aurelius.domain.entities.enums import Currency
from aurelius.domain.entities.financials import (
    CanonicalConcept,
    FinancialConcept,
    FinancialFact,
    FinancialPeriod,
    PeriodType,
    Scale,
    StatementType,
    Unit,
)


@pytest.fixture
def sample_period() -> FinancialPeriod:
    return FinancialPeriod(
        period_type=PeriodType.DURATION,
        end_date=date(2024, 9, 30),
    )


@pytest.fixture
def sample_concept() -> FinancialConcept:
    return FinancialConcept(
        source_concept="Total Revenue",
        canonical_concept=CanonicalConcept.REVENUE,
        statement_type=StatementType.INCOME_STATEMENT,
    )


def test_financial_fact_decimal_precision(sample_period, sample_concept):
    """
    FinancialFact.value strictly preserves exact Decimal precision without float conversion.
    """
    exact_value = Decimal("416161000000")
    fact = FinancialFact(
        fact_id="AAPL_INCOME_2024-09-30_Total_Revenue",
        company_id="AAPL",
        concept=sample_concept,
        value=exact_value,
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        scale=Scale.UNITS,
        period=sample_period,
    )
    assert isinstance(fact.value, Decimal)
    assert fact.value == exact_value
    # Value must not be float
    assert not isinstance(fact.value, float)


def test_unit_currency_orthogonality_currency_requires_currency(
    sample_period, sample_concept
):
    """
    unit=CURRENCY requires a valid non-null Currency.
    """
    with pytest.raises(ValueError, match="unit=CURRENCY must specify a known currency"):
        FinancialFact(
            fact_id="fact_1",
            company_id="AAPL",
            concept=sample_concept,
            value=Decimal("1000"),
            unit=Unit.CURRENCY,
            currency=None,
            period=sample_period,
        )


def test_unit_shares_mandates_currency_none(sample_period):
    """
    unit=SHARES mandates currency=None (shares are counted, not currency denominated).
    """
    shares_concept = FinancialConcept(
        source_concept="Ordinary Shares Number",
        statement_type=StatementType.BALANCE_SHEET,
    )
    # Valid shares fact
    fact = FinancialFact(
        fact_id="fact_shares",
        company_id="AAPL",
        concept=shares_concept,
        value=Decimal("15500000000"),
        unit=Unit.SHARES,
        currency=None,
        scale=Scale.UNITS,
        period=sample_period,
    )
    assert fact.unit == Unit.SHARES
    assert fact.currency is None

    # Invalid: shares with currency specified
    with pytest.raises(ValueError, match="unit=SHARES must have currency=None"):
        FinancialFact(
            fact_id="fact_invalid",
            company_id="AAPL",
            concept=shares_concept,
            value=Decimal("15500000000"),
            unit=Unit.SHARES,
            currency=Currency.USD,
            period=sample_period,
        )


def test_scale_multipliers():
    """
    Scale enum multipliers evaluate correctly to Decimals.
    """
    assert Scale.UNITS.multiplier == Decimal("1")
    assert Scale.THOUSANDS.multiplier == Decimal("1000")
    assert Scale.MILLIONS.multiplier == Decimal("1000000")
    assert Scale.BILLIONS.multiplier == Decimal("1000000000")


def test_provenance_and_dimensions_preserved(sample_period, sample_concept):
    """
    Financial facts preserve audit provenance and dimensional context dictionaries.
    """
    dims = {"segment": "iPhone", "geography": "Americas"}
    prov = {"provider": "yahoo_finance", "source_row": "Total Revenue"}

    fact = FinancialFact(
        fact_id="fact_dims",
        company_id="AAPL",
        concept=sample_concept,
        value=Decimal("200000000"),
        unit=Unit.CURRENCY,
        currency=Currency.USD,
        scale=Scale.UNITS,
        period=sample_period,
        dimensions=dims,
        provenance=prov,
        is_restated=True,
    )
    assert fact.dimensions == dims
    assert fact.provenance == prov
    assert fact.is_restated is True
