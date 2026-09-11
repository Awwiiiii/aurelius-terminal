"""
tests/unit/domain/test_domain_entities.py
=========================================
Unit tests for domain entities and immutability guarantees.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurelius.domain.entities import (
    AssetType,
    Currency,
    MarketInterval,
    MarketState,
    OHLCVBar,
    OHLCVSeries,
    Price,
    PriceChange,
    Quote,
    Security,
)


def test_price_immutability_and_decimal_types() -> None:
    ts = datetime(2024, 1, 2, 16, 0, tzinfo=UTC)
    price = Price(
        amount=Decimal("185.64"),
        currency=Currency.USD,
        timestamp=ts,
        source="yahoo_finance",
    )
    assert price.amount == Decimal("185.64")
    assert price.currency == Currency.USD
    assert price.timestamp == ts
    assert price.source == "yahoo_finance"

    with pytest.raises(ValidationError):
        # Entity is frozen (immutable)
        price.amount = Decimal("200.00")  # type: ignore[misc]


def test_price_change() -> None:
    change = PriceChange(
        absolute=Decimal("2.50"),
        percent=Decimal("1.36"),
    )
    assert change.absolute == Decimal("2.50")
    assert change.percent == Decimal("1.36")


def test_quote_entity_creation_and_volume_as_int() -> None:
    ts = datetime(2024, 1, 2, 21, 0, tzinfo=UTC)
    quote = Quote(
        ticker="AAPL",
        price=Decimal("185.64"),
        timestamp=ts,
        currency=Currency.USD,
        change=Decimal("-0.40"),
        change_percent=Decimal("-0.21"),
        volume=82488700,
        open=Decimal("187.15"),
        high=Decimal("188.44"),
        low=Decimal("183.89"),
        previous_close=Decimal("186.04"),
        market_state=MarketState.CLOSED,
        provider="yahoo_finance",
        is_delayed=True,
    )
    assert quote.ticker == "AAPL"
    assert quote.price == Decimal("185.64")
    assert isinstance(quote.volume, int)
    assert quote.volume == 82488700
    assert quote.is_delayed is True


def test_quote_immutability() -> None:
    quote = Quote(
        ticker="MSFT",
        price=Decimal("400.00"),
        timestamp=datetime.now(UTC),
        provider="yahoo_finance",
    )
    with pytest.raises(ValidationError):
        quote.price = Decimal("401.00")  # type: ignore[misc]


def test_ohlcv_bar_entity() -> None:
    bar = OHLCVBar(
        timestamp=date(2024, 1, 2),
        open=Decimal("187.15"),
        high=Decimal("188.44"),
        low=Decimal("183.89"),
        close=Decimal("185.64"),
        volume=82488700,
        adj_close=Decimal("184.25"),
    )
    assert bar.timestamp == date(2024, 1, 2)
    assert bar.open == Decimal("187.15")
    assert isinstance(bar.volume, int)
    assert bar.volume == 82488700
    assert bar.adj_close == Decimal("184.25")

    with pytest.raises(ValidationError):
        bar.close = Decimal("190.00")  # type: ignore[misc]


def test_ohlcv_series_is_adjusted_semantics() -> None:
    bar = OHLCVBar(
        timestamp=date(2024, 1, 2),
        open=Decimal("187.15"),
        high=Decimal("188.44"),
        low=Decimal("183.89"),
        close=Decimal("185.64"),
        volume=82488700,
        adj_close=Decimal("184.25"),
    )
    series = OHLCVSeries(
        ticker="AAPL",
        interval=MarketInterval.DAILY,
        bars=[bar],
        provider="yahoo_finance",
        is_adjusted=True,
    )
    assert series.ticker == "AAPL"
    assert series.interval == MarketInterval.DAILY
    assert series.is_adjusted is True
    # Raw close remains raw
    assert series.bars[0].close == Decimal("185.64")
    assert series.bars[0].adj_close == Decimal("184.25")


def test_market_interval_m1_restriction() -> None:
    # M1 is explicitly restricted to daily interval
    assert MarketInterval.DAILY.value == "1d"
    assert len(list(MarketInterval)) == 1


def test_security_entity() -> None:
    sec = Security(
        ticker="NVDA",
        name="NVIDIA Corporation",
        asset_type=AssetType.EQUITY,
        currency=Currency.USD,
        exchange="NASDAQ",
        country="USA",
        sector="Technology",
        industry="Semiconductors",
        provider="yahoo_finance",
        fetched_at=datetime.now(UTC),
    )
    assert sec.ticker == "NVDA"
    assert sec.asset_type == AssetType.EQUITY
