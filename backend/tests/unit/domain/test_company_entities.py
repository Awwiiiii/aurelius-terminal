"""
tests/unit/domain/test_company_entities.py
==========================================
Unit tests for CompanyProfile and SecuritySearchResult domain entities.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurelius.domain.entities import (
    AssetType,
    CompanyProfile,
    Currency,
    Security,
    SecuritySearchResult,
)
from aurelius.domain.errors import DataQualityError
from aurelius.domain.validation import validate_company_profile


def test_company_profile_entity_and_immutability() -> None:
    now = datetime(2026, 9, 11, 16, 0, tzinfo=UTC)
    profile = CompanyProfile(
        lookup_ticker="AAPL",
        company_name="Apple Inc.",
        legal_name="Apple Inc.",
        description="Apple designs smartphones, computers, and tablets.",
        sector="Technology",
        industry="Consumer Electronics",
        country="United States",
        state="California",
        city="Cupertino",
        address="One Apple Park Way",
        website="https://www.apple.com",
        employees=150000,
        provider="yahoo_finance",
        fetched_at=now,
    )
    assert profile.lookup_ticker == "AAPL"
    assert profile.company_name == "Apple Inc."
    assert profile.sector == "Technology"
    assert profile.employees == 150000
    assert profile.provider == "yahoo_finance"

    # Verify immutability
    with pytest.raises(ValidationError):
        profile.company_name = "New Apple Inc."  # type: ignore[misc]


def test_missing_optional_fields_remain_none() -> None:
    now = datetime(2026, 9, 11, 16, 0, tzinfo=UTC)
    profile = CompanyProfile(
        lookup_ticker="MINIMAL",
        company_name="Minimal Corp",
        provider="yahoo_finance",
        fetched_at=now,
    )
    # Never fabricated with plausible defaults!
    assert profile.description is None
    assert profile.sector is None
    assert profile.industry is None
    assert profile.country is None
    assert profile.employees is None
    assert profile.website is None


def test_negative_employees_fails_validation() -> None:
    now = datetime(2026, 9, 11, 16, 0, tzinfo=UTC)
    bad_profile = CompanyProfile(
        lookup_ticker="BAD",
        company_name="Bad Employees Corp",
        employees=-50,
        provider="yahoo_finance",
        fetched_at=now,
    )
    with pytest.raises(DataQualityError) as exc:
        validate_company_profile(bad_profile)
    assert exc.value.check == "non_negative_employees"


def test_security_currency_defaults_to_unknown_not_usd() -> None:
    now = datetime(2026, 9, 11, 16, 0, tzinfo=UTC)
    sec = Security(
        ticker="FOREIGN",
        name="Foreign Company",
        provider="yahoo_finance",
        fetched_at=now,
    )
    # Strict financial correctness: never default to USD!
    assert sec.currency == Currency.UNKNOWN
    assert sec.currency != Currency.USD


def test_security_search_result_preserves_none_currency() -> None:
    res = SecuritySearchResult(
        ticker="UNKNOWN",
        name="Unknown Asset",
        asset_type=AssetType.EQUITY,
        provider="yahoo_finance",
    )
    assert res.currency is None
    assert res.currency != Currency.USD
