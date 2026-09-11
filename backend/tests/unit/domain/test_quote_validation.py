"""
tests/unit/domain/test_quote_validation.py
==========================================
Unit tests for quote validation and sanity checks.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from aurelius.domain.entities import Currency, Quote
from aurelius.domain.errors import DataQualityError, InvalidTickerError
from aurelius.domain.validation import validate_quote


def create_valid_quote(
    ticker: str = "AAPL",
    price: Decimal = Decimal("185.00"),
    high: Decimal | None = Decimal("186.00"),
    low: Decimal | None = Decimal("184.00"),
    volume: int | None = 1000000,
) -> Quote:
    return Quote(
        ticker=ticker,
        price=price,
        timestamp=datetime(2024, 1, 2, 16, 0, tzinfo=UTC),
        currency=Currency.USD,
        high=high,
        low=low,
        volume=volume,
        provider="yahoo_finance",
    )


def test_valid_quote_passes() -> None:
    quote = create_valid_quote()
    validate_quote(quote)


def test_zero_or_negative_quote_price_fails() -> None:
    quote_zero = create_valid_quote(price=Decimal("0.00"))
    with pytest.raises(DataQualityError) as exc:
        validate_quote(quote_zero)
    assert exc.value.check == "positive_price"

    quote_neg = create_valid_quote(price=Decimal("-10.00"))
    with pytest.raises(DataQualityError) as exc2:
        validate_quote(quote_neg)
    assert exc2.value.check == "positive_price"


def test_quote_high_less_than_low_fails() -> None:
    quote = create_valid_quote(high=Decimal("180.00"), low=Decimal("185.00"))
    with pytest.raises(DataQualityError) as exc:
        validate_quote(quote)
    assert exc.value.check == "high_gte_low"


def test_quote_negative_volume_fails() -> None:
    quote = create_valid_quote(volume=-100)
    with pytest.raises(DataQualityError) as exc:
        validate_quote(quote)
    assert exc.value.check == "non_negative_volume"


def test_quote_invalid_ticker_fails() -> None:
    quote = create_valid_quote(ticker="INVALID!!TICKER")
    with pytest.raises(InvalidTickerError):
        validate_quote(quote)
