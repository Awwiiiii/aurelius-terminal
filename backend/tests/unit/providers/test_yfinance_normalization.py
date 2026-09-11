"""
tests/unit/providers/test_yfinance_normalization.py
==================================================
Unit tests for YFinanceProvider DataFrame normalization and retry logic.
"""

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
import requests

from aurelius.domain.entities import MarketInterval
from aurelius.domain.errors import (
    DataNotFoundError,
    DataQualityError,
    InvalidTickerError,
    ProviderRateLimitError,
)
from aurelius.providers.yfinance_provider import (
    YFinanceProvider,
    _is_transient_error,
)


@pytest.fixture
def provider() -> YFinanceProvider:
    return YFinanceProvider()


@pytest.fixture
def sample_yfinance_dataframe() -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=3, freq="D")
    data = {
        "Open": [187.15, 184.22, 182.15],
        "High": [188.44, 185.88, 183.08],
        "Low": [183.89, 183.43, 180.88],
        "Close": [185.64, 184.25, 181.91],
        "Volume": [82488700, 58414500, 71983600],
        "Adj Close": [184.75, 183.37, 181.04],
    }
    return pd.DataFrame(data, index=dates)


def test_normalize_valid_dataframe(
    provider: YFinanceProvider, sample_yfinance_dataframe: pd.DataFrame
) -> None:
    series = provider.normalize_dataframe(
        sample_yfinance_dataframe,
        ticker="AAPL",
        start=date(2024, 1, 2),
        end=date(2024, 1, 4),
    )
    assert series.ticker == "AAPL"
    assert series.interval == MarketInterval.DAILY
    assert series.provider == "yahoo_finance"
    assert series.is_adjusted is True
    assert len(series.bars) == 3

    first_bar = series.bars[0]
    assert first_bar.timestamp == date(2024, 1, 2)
    assert first_bar.open == Decimal("187.15")
    assert first_bar.high == Decimal("188.44")
    assert first_bar.low == Decimal("183.89")
    assert first_bar.close == Decimal("185.64")
    assert isinstance(first_bar.volume, int)
    assert first_bar.volume == 82488700
    assert first_bar.adj_close == Decimal("184.75")


def test_normalize_empty_dataframe_raises_not_found(provider: YFinanceProvider) -> None:
    empty_df = pd.DataFrame()
    with pytest.raises(DataNotFoundError) as exc:
        provider.normalize_dataframe(
            empty_df, ticker="INVALID", start=date(2024, 1, 1), end=date(2024, 1, 10)
        )
    assert exc.value.ticker == "INVALID"


def test_normalize_missing_columns_raises_quality_error(
    provider: YFinanceProvider,
) -> None:
    dates = pd.date_range("2024-01-02", periods=2, freq="D")
    bad_df = pd.DataFrame(
        {"Open": [100.0, 101.0], "Close": [102.0, 103.0]}, index=dates
    )
    with pytest.raises(DataQualityError) as exc:
        provider.normalize_dataframe(
            bad_df, ticker="TEST", start=date(2024, 1, 2), end=date(2024, 1, 3)
        )
    assert exc.value.check == "required_columns"


def test_normalize_filters_dates_strictly(
    provider: YFinanceProvider, sample_yfinance_dataframe: pd.DataFrame
) -> None:
    # Only request 2024-01-03 to 2024-01-03
    series = provider.normalize_dataframe(
        sample_yfinance_dataframe,
        ticker="AAPL",
        start=date(2024, 1, 3),
        end=date(2024, 1, 3),
    )
    assert len(series.bars) == 1
    assert series.bars[0].timestamp == date(2024, 1, 3)


def test_normalize_invalid_prices_raises_quality_error(
    provider: YFinanceProvider,
) -> None:
    dates = pd.date_range("2024-01-02", periods=1, freq="D")
    invalid_data = {
        "Open": [100.0],
        "High": [90.0],  # High < Low
        "Low": [95.0],
        "Close": [92.0],
        "Volume": [1000],
    }
    df = pd.DataFrame(invalid_data, index=dates)
    with pytest.raises(DataQualityError):
        provider.normalize_dataframe(
            df, ticker="TEST", start=date(2024, 1, 2), end=date(2024, 1, 2)
        )


def test_transient_error_classification() -> None:
    # Non-retryable
    assert _is_transient_error(InvalidTickerError("bad ticker")) is False
    assert _is_transient_error(DataNotFoundError("no data")) is False
    assert _is_transient_error(DataQualityError("bad price")) is False
    assert _is_transient_error(ProviderRateLimitError("rate limited")) is False

    # 429 HTTP error is NOT transient
    resp_429 = requests.Response()
    resp_429.status_code = 429
    http_429 = requests.exceptions.HTTPError(response=resp_429)
    assert _is_transient_error(http_429) is False

    # 404 HTTP error is NOT transient
    resp_404 = requests.Response()
    resp_404.status_code = 404
    http_404 = requests.exceptions.HTTPError(response=resp_404)
    assert _is_transient_error(http_404) is False

    # Retryable: connection timeout
    assert _is_transient_error(requests.exceptions.Timeout("timeout")) is True
    assert (
        _is_transient_error(requests.exceptions.ConnectionError("connection dropped"))
        is True
    )

    # Retryable: 502/503/504
    for code in (500, 502, 503, 504):
        resp = requests.Response()
        resp.status_code = code
        assert _is_transient_error(requests.exceptions.HTTPError(response=resp)) is True
