"""
aurelius.domain.validation
==========================
Financial domain validation rules and data quality checks.

These functions enforce financial and numerical correctness across domain entities.
Data that fails sanity or quality checks raises domain exceptions from `aurelius.domain.errors`.
"""

import re
from decimal import Decimal

from aurelius.domain.entities.company import CompanyProfile
from aurelius.domain.entities.ohlcv import OHLCVBar, OHLCVSeries
from aurelius.domain.entities.quote import Quote
from aurelius.domain.errors import (
    DataNotFoundError,
    DataQualityError,
    InvalidSearchQueryError,
    InvalidTickerError,
)

# Ticker grammar permitting:
# - Alphanumeric characters (A-Z, 0-9)
# - '.' and '-' for share classes (BRK.B, BRK-B) and foreign exchanges (AAPL.TO)
# - '^' for market index benchmarks (^GSPC, ^DJI, ^IXIC, ^VIX)
# - '=' for continuous futures symbols (ES=F, NQ=F)
TICKER_REGEX = re.compile(r"^[A-Z0-9.\-=^]{1,12}$")

FORBIDDEN_QUERY_CHARS = re.compile(r"[\x00-\x1f\x7f<>]")


def validate_ticker(ticker: str) -> str:
    """
    Validate and normalize a security ticker symbol.

    Normalization:
      - Strips leading/trailing whitespace
      - Converts to uppercase

    Validation grammar (1-12 characters):
      - Standard symbols: Alphanumeric (e.g. 'AAPL', 'MSFT')
      - Share classes / foreign listings: '.' and '-' (e.g. 'BRK.B', 'BRK-B', 'AAPL.TO')
      - Market indices: Caret '^' (e.g. '^GSPC' for S&P 500, '^DJI', '^IXIC')
      - Futures: Equals '=' (e.g. 'ES=F' for E-mini S&P 500 futures)

    Raises:
      InvalidTickerError: If the ticker is empty, malformed, or exceeds length limits.
    """
    if not isinstance(ticker, str):
        raise InvalidTickerError(
            message=f"Ticker must be a string, got {type(ticker).__name__}",
            ticker=str(ticker),
        )

    normalized = ticker.strip().upper()
    if not normalized:
        raise InvalidTickerError(
            message="Ticker symbol cannot be empty",
            ticker=ticker,
        )

    if not TICKER_REGEX.match(normalized):
        raise InvalidTickerError(
            message=(
                f"Invalid ticker format: '{ticker}'. "
                "Tickers must be 1 to 12 alphanumeric characters, optionally containing '.', '-', '^', or '='."
            ),
            ticker=normalized,
        )

    return normalized


def validate_search_query(query: str) -> str:
    """
    Validate and normalize a freeform security/company search query.

    Distinction from ticker validation:
      - Search queries support full company names (e.g. 'Apple Inc.', 'Microsoft Technology')
      - Spaces and case are preserved (spaces collapsed to single spaces)
      - Does NOT enforce ticker uppercase regex

    Validation:
      - Query must be a string
      - Must be non-empty after stripping leading/trailing whitespace
      - Length: 1 <= len <= 60 characters
      - Rejects non-printable control characters, null bytes, and script injection (<, >)

    Raises:
      InvalidSearchQueryError: If query is empty, too long, or contains forbidden characters.
    """
    if not isinstance(query, str):
        raise InvalidSearchQueryError(
            message=f"Search query must be a string, got {type(query).__name__}",
            query=str(query),
        )

    if FORBIDDEN_QUERY_CHARS.search(query):
        raise InvalidSearchQueryError(
            message="Search query contains forbidden control or script characters",
            query=query,
        )

    # Collapse multiple internal whitespace to single space
    cleaned = re.sub(r"\s+", " ", query.strip())
    if not cleaned:
        raise InvalidSearchQueryError(
            message="Search query cannot be empty",
            query=query,
        )

    if len(cleaned) > 60:
        raise InvalidSearchQueryError(
            message=f"Search query exceeds maximum length of 60 characters (got {len(cleaned)})",
            query=cleaned,
        )

    return cleaned


def validate_company_profile(profile: CompanyProfile) -> None:
    """
    Validate company profile invariants.

    Invariants:
      - Employee count must be non-negative if reported
    """
    if profile.employees is not None and profile.employees < 0:
        raise DataQualityError(
            message=f"Employee count cannot be negative, got {profile.employees}",
            check="non_negative_employees",
            ticker=profile.lookup_ticker,
        )


def validate_ohlcv_bar(bar: OHLCVBar, ticker: str | None = None) -> None:
    """
    Perform financial integrity checks on a single OHLCV bar.

    Financial invariants:
      - Prices must be strictly positive (> 0)
      - High must be >= Low
      - High must be >= Open and High >= Close
      - Low must be <= Open and Low <= Close
      - Volume must be >= 0
      - If present, adj_close must be > 0

    Raises:
      DataQualityError: If any financial invariant is violated.
    """
    zero = Decimal("0")

    # Positive price checks
    if bar.open <= zero or bar.high <= zero or bar.low <= zero or bar.close <= zero:
        raise DataQualityError(
            message=f"OHLC prices must be strictly positive. Got Open={bar.open}, High={bar.high}, Low={bar.low}, Close={bar.close}",
            check="positive_prices",
            ticker=ticker,
        )

    # Invariant: High >= Low
    if bar.high < bar.low:
        raise DataQualityError(
            message=f"High price ({bar.high}) cannot be less than low price ({bar.low})",
            check="high_gte_low",
            ticker=ticker,
        )

    # Invariant: High >= Open and High >= Close
    if bar.high < bar.open:
        raise DataQualityError(
            message=f"High price ({bar.high}) cannot be less than open price ({bar.open})",
            check="high_gte_open",
            ticker=ticker,
        )
    if bar.high < bar.close:
        raise DataQualityError(
            message=f"High price ({bar.high}) cannot be less than close price ({bar.close})",
            check="high_gte_close",
            ticker=ticker,
        )

    # Invariant: Low <= Open and Low <= Close
    if bar.low > bar.open:
        raise DataQualityError(
            message=f"Low price ({bar.low}) cannot be greater than open price ({bar.open})",
            check="low_lte_open",
            ticker=ticker,
        )
    if bar.low > bar.close:
        raise DataQualityError(
            message=f"Low price ({bar.low}) cannot be greater than close price ({bar.close})",
            check="low_lte_close",
            ticker=ticker,
        )

    # Invariant: Volume >= 0
    if bar.volume < 0:
        raise DataQualityError(
            message=f"Volume ({bar.volume}) cannot be negative",
            check="non_negative_volume",
            ticker=ticker,
        )

    # Invariant: Adjusted close > 0 if present
    if bar.adj_close is not None and bar.adj_close <= zero:
        raise DataQualityError(
            message=f"Adjusted close ({bar.adj_close}) must be strictly positive",
            check="positive_adj_close",
            ticker=ticker,
        )


def validate_ohlcv_series(series: OHLCVSeries) -> None:
    """
    Perform financial integrity and ordering checks on a full OHLCV series.

    Checks:
      - Ticker is valid
      - Series has at least one bar (raises DataNotFoundError if empty)
      - Bar timestamps are strictly monotonically increasing (no duplicate dates or out-of-order bars)
      - Each individual bar satisfies validate_ohlcv_bar

    Raises:
      DataNotFoundError: If the series contains 0 bars.
      DataQualityError: If ordering is violated or any bar fails sanity checks.
    """
    validate_ticker(series.ticker)

    if not series.bars:
        raise DataNotFoundError(
            message=f"No OHLCV bars found for ticker '{series.ticker}'",
            ticker=series.ticker,
        )

    prev_date = None
    for bar in series.bars:
        if prev_date is not None and bar.timestamp <= prev_date:
            raise DataQualityError(
                message=(
                    f"OHLCV bars must be strictly chronologically increasing. "
                    f"Found timestamp {bar.timestamp} following {prev_date}"
                ),
                check="monotonic_timestamps",
                ticker=series.ticker,
            )
        prev_date = bar.timestamp
        validate_ohlcv_bar(bar, ticker=series.ticker)


def validate_quote(quote: Quote) -> None:
    """
    Perform financial sanity checks on a market quote snapshot.

    Checks:
      - Ticker is valid
      - Price is strictly positive
      - Day High >= Day Low (if both present)
      - Volume >= 0 (if present)

    Raises:
      DataQualityError: If quote values violate financial sanity checks.
    """
    validate_ticker(quote.ticker)

    zero = Decimal("0")
    if quote.price <= zero:
        raise DataQualityError(
            message=f"Quote price must be strictly positive, got {quote.price}",
            check="positive_price",
            ticker=quote.ticker,
        )

    if quote.high is not None and quote.low is not None and quote.high < quote.low:
        raise DataQualityError(
            message=f"Quote day high ({quote.high}) cannot be less than day low ({quote.low})",
            check="high_gte_low",
            ticker=quote.ticker,
        )

    if quote.volume is not None and quote.volume < 0:
        raise DataQualityError(
            message=f"Quote volume ({quote.volume}) cannot be negative",
            check="non_negative_volume",
            ticker=quote.ticker,
        )
