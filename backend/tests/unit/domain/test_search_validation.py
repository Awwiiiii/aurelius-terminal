"""
tests/unit/domain/test_search_validation.py
===========================================
Unit tests for search query validation vs ticker validation separation.
"""

import pytest

from aurelius.domain.errors import InvalidSearchQueryError, InvalidTickerError
from aurelius.domain.validation import validate_search_query, validate_ticker


def test_search_query_with_spaces_passes() -> None:
    assert validate_search_query("Apple Inc.") == "Apple Inc."
    assert validate_search_query("Microsoft Corporation") == "Microsoft Corporation"
    assert validate_search_query("SPDR S&P 500 ETF") == "SPDR S&P 500 ETF"
    assert (
        validate_search_query("Berkshire Hathaway Class B")
        == "Berkshire Hathaway Class B"
    )


def test_search_query_whitespace_collapsing() -> None:
    assert validate_search_query("   Apple     Inc.   ") == "Apple Inc."


def test_search_query_empty_or_whitespace_fails() -> None:
    with pytest.raises(InvalidSearchQueryError):
        validate_search_query("")
    with pytest.raises(InvalidSearchQueryError):
        validate_search_query("    ")


def test_search_query_length_limits() -> None:
    # 60 chars passes
    valid_long = "A" * 60
    assert validate_search_query(valid_long) == valid_long

    # 61 chars fails
    too_long = "A" * 61
    with pytest.raises(InvalidSearchQueryError):
        validate_search_query(too_long)


def test_search_query_forbidden_chars() -> None:
    with pytest.raises(InvalidSearchQueryError):
        validate_search_query("<script>alert(1)</script>")
    with pytest.raises(InvalidSearchQueryError):
        validate_search_query("Apple\x00Corp")
    with pytest.raises(InvalidSearchQueryError):
        validate_search_query("Apple\nInc")


def test_search_query_vs_ticker_validation_separation() -> None:
    query = "Apple Inc."
    # Valid for search
    assert validate_search_query(query) == "Apple Inc."
    # Strictly invalid for ticker routing grammar (contains spaces)
    with pytest.raises(InvalidTickerError):
        validate_ticker(query)


def test_special_ticker_syntax_supported() -> None:
    # Indices with caret
    assert validate_ticker("^GSPC") == "^GSPC"
    assert validate_ticker("^DJI") == "^DJI"
    assert validate_ticker("^IXIC") == "^IXIC"
    assert validate_ticker("^VIX") == "^VIX"

    # Futures with equals
    assert validate_ticker("ES=F") == "ES=F"
    assert validate_ticker("NQ=F") == "NQ=F"

    # Share classes with dot or dash
    assert validate_ticker("BRK.B") == "BRK.B"
    assert validate_ticker("BRK-B") == "BRK-B"
    assert validate_ticker("AAPL.TO") == "AAPL.TO"
