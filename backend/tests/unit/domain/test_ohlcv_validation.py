"""
tests/unit/domain/test_ohlcv_validation.py
==========================================
Unit tests for OHLCV validation and financial integrity rules.
"""

from datetime import date
from decimal import Decimal

import pytest

from aurelius.domain.entities import MarketInterval, OHLCVBar, OHLCVSeries
from aurelius.domain.errors import DataNotFoundError, DataQualityError
from aurelius.domain.validation import validate_ohlcv_bar, validate_ohlcv_series


def create_valid_bar(
    timestamp: date = date(2024, 1, 2),
    open_: Decimal = Decimal("100.00"),
    high: Decimal = Decimal("105.00"),
    low: Decimal = Decimal("95.00"),
    close: Decimal = Decimal("102.00"),
    volume: int = 1000000,
    adj_close: Decimal | None = Decimal("102.00"),
) -> OHLCVBar:
    return OHLCVBar(
        timestamp=timestamp,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        adj_close=adj_close,
    )


def test_valid_bar_passes() -> None:
    bar = create_valid_bar()
    # Should not raise
    validate_ohlcv_bar(bar, ticker="TEST")


def test_high_less_than_low_fails() -> None:
    bar = create_valid_bar(high=Decimal("90.00"), low=Decimal("95.00"))
    with pytest.raises(DataQualityError) as exc_info:
        validate_ohlcv_bar(bar, ticker="TEST")
    assert exc_info.value.check == "high_gte_low"


def test_high_less_than_open_fails() -> None:
    bar = create_valid_bar(open_=Decimal("110.00"), high=Decimal("105.00"))
    with pytest.raises(DataQualityError) as exc_info:
        validate_ohlcv_bar(bar, ticker="TEST")
    assert exc_info.value.check == "high_gte_open"


def test_high_less_than_close_fails() -> None:
    bar = create_valid_bar(close=Decimal("110.00"), high=Decimal("105.00"))
    with pytest.raises(DataQualityError) as exc_info:
        validate_ohlcv_bar(bar, ticker="TEST")
    assert exc_info.value.check == "high_gte_close"


def test_low_greater_than_open_fails() -> None:
    bar = create_valid_bar(open_=Decimal("90.00"), low=Decimal("95.00"))
    with pytest.raises(DataQualityError) as exc_info:
        validate_ohlcv_bar(bar, ticker="TEST")
    assert exc_info.value.check == "low_lte_open"


def test_low_greater_than_close_fails() -> None:
    bar = create_valid_bar(close=Decimal("90.00"), low=Decimal("95.00"))
    with pytest.raises(DataQualityError) as exc_info:
        validate_ohlcv_bar(bar, ticker="TEST")
    assert exc_info.value.check == "low_lte_close"


def test_zero_or_negative_prices_fail() -> None:
    bar_zero = create_valid_bar(close=Decimal("0.00"))
    with pytest.raises(DataQualityError) as exc_info:
        validate_ohlcv_bar(bar_zero, ticker="TEST")
    assert exc_info.value.check == "positive_prices"

    bar_neg = create_valid_bar(open_=Decimal("-10.00"))
    with pytest.raises(DataQualityError) as exc_info2:
        validate_ohlcv_bar(bar_neg, ticker="TEST")
    assert exc_info2.value.check == "positive_prices"


def test_negative_volume_fails() -> None:
    bar = create_valid_bar(volume=-500)
    with pytest.raises(DataQualityError) as exc_info:
        validate_ohlcv_bar(bar, ticker="TEST")
    assert exc_info.value.check == "non_negative_volume"


def test_negative_or_zero_adj_close_fails() -> None:
    bar = create_valid_bar(adj_close=Decimal("0.00"))
    with pytest.raises(DataQualityError) as exc_info:
        validate_ohlcv_bar(bar, ticker="TEST")
    assert exc_info.value.check == "positive_adj_close"


def test_valid_series_passes() -> None:
    bars = [
        create_valid_bar(timestamp=date(2024, 1, 2)),
        create_valid_bar(timestamp=date(2024, 1, 3)),
        create_valid_bar(timestamp=date(2024, 1, 4)),
    ]
    series = OHLCVSeries(
        ticker="AAPL",
        interval=MarketInterval.DAILY,
        bars=bars,
        provider="yahoo_finance",
        is_adjusted=True,
    )
    validate_ohlcv_series(series)


def test_empty_series_raises_data_not_found() -> None:
    series = OHLCVSeries(
        ticker="AAPL",
        interval=MarketInterval.DAILY,
        bars=[],
        provider="yahoo_finance",
    )
    with pytest.raises(DataNotFoundError) as exc_info:
        validate_ohlcv_series(series)
    assert exc_info.value.ticker == "AAPL"


def test_non_monotonic_series_fails() -> None:
    bars = [
        create_valid_bar(timestamp=date(2024, 1, 3)),
        create_valid_bar(timestamp=date(2024, 1, 2)),  # Out of order
    ]
    series = OHLCVSeries(
        ticker="AAPL",
        interval=MarketInterval.DAILY,
        bars=bars,
        provider="yahoo_finance",
    )
    with pytest.raises(DataQualityError) as exc_info:
        validate_ohlcv_series(series)
    assert exc_info.value.check == "monotonic_timestamps"


def test_duplicate_dates_in_series_fails() -> None:
    bars = [
        create_valid_bar(timestamp=date(2024, 1, 2)),
        create_valid_bar(timestamp=date(2024, 1, 2)),  # Duplicate
    ]
    series = OHLCVSeries(
        ticker="AAPL",
        interval=MarketInterval.DAILY,
        bars=bars,
        provider="yahoo_finance",
    )
    with pytest.raises(DataQualityError) as exc_info:
        validate_ohlcv_series(series)
    assert exc_info.value.check == "monotonic_timestamps"
