"""
tests/unit/domain/test_ticker_validation.py
===========================================
Unit tests for ticker validation and normalization.
"""

import pytest

from aurelius.domain.errors import InvalidTickerError
from aurelius.domain.validation import validate_ticker


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("aapl", "AAPL"),
        ("  msft  ", "MSFT"),
        ("BRK.B", "BRK.B"),
        ("brk-b", "BRK-B"),
        ("BTC-USD", "BTC-USD"),
        ("^GSPC", "^GSPC"),
        ("ES=F", "ES=F"),
        ("spy", "SPY"),
    ],
)
def test_valid_ticker_normalization(raw: str, expected: str) -> None:
    assert validate_ticker(raw) == expected


@pytest.mark.parametrize(
    "invalid_raw",
    [
        "",
        "   ",
        "AAPL!",
        "MSFT$CORP",
        "A" * 15,
        "INVALID/TICKER",
        "SPY;DROP TABLE",
    ],
)
def test_invalid_ticker_rejection(invalid_raw: str) -> None:
    with pytest.raises(InvalidTickerError) as exc_info:
        validate_ticker(invalid_raw)
    assert exc_info.value.ticker is not None or invalid_raw == ""


def test_non_string_ticker_rejection() -> None:
    with pytest.raises(InvalidTickerError):
        validate_ticker(123)  # type: ignore[arg-type]
