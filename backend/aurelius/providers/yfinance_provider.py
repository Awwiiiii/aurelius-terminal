"""
aurelius.providers.yfinance_provider
====================================
Yahoo Finance data provider implementation using `yfinance`.

Design principles:
  1. Thread-safe offloading:
     `yfinance` is a synchronous, blocking HTTP library. All calls to `yfinance`
     are executed in a worker thread via `asyncio.to_thread` so the FastAPI
     asynchronous event loop is never blocked.

  2. Selective Retry Policy:
     - Retries ONLY explicitly classified transient network/provider failures
       (e.g., connection timeouts, connection resets, HTTP 500/502/503/504).
     - NEVER retries:
         * `InvalidTickerError` (client error)
         * `DataNotFoundError` (empty data / delisted / no records)
         * `DataQualityError` (validation failures)
         * `ProviderRateLimitError` (HTTP 429 - caller must back off)

  3. Financial Correctness:
     - OHLC prices are retrieved with `auto_adjust=False` to preserve true historical
       unadjusted trade execution prices.
     - Adjusted closing prices from Yahoo Finance are normalized into `adj_close`.
     - `is_adjusted` is set to True to indicate `adj_close` is present; raw OHLC
       remains strictly unadjusted.
     - Volume is stored as an integer share count (`int`).
     - Floats are converted to `Decimal` using string representation: `Decimal(str(val))`.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
import requests
import yfinance as yf

from aurelius.domain.entities.company import CompanyProfile
from aurelius.domain.entities.enums import (
    AssetType,
    Currency,
    MarketInterval,
    MarketState,
)
from aurelius.domain.entities.ohlcv import OHLCVBar, OHLCVSeries
from aurelius.domain.entities.quote import Quote
from aurelius.domain.entities.search import SecuritySearchResult
from aurelius.domain.entities.security import Security
from aurelius.domain.errors import (
    DataNotFoundError,
    DataQualityError,
    InvalidSearchQueryError,
    InvalidTickerError,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from aurelius.domain.validation import (
    validate_company_profile,
    validate_ohlcv_series,
    validate_quote,
    validate_search_query,
    validate_ticker,
)
from aurelius.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)


def _map_quote_type(raw_type: str | None) -> AssetType:
    """
    Map provider quote type / display type string to canonical AssetType enum.
    """
    if not raw_type:
        return AssetType.UNKNOWN
    normalized = raw_type.strip().upper()
    if normalized in ("EQUITY", "COMMON STOCK"):
        return AssetType.EQUITY
    if normalized in ("ETF", "ETP", "EXCHANGE TRADED FUND"):
        return AssetType.ETF
    if normalized in ("INDEX", "INDICES"):
        return AssetType.INDEX
    if normalized in ("MUTUALFUND", "MUTUAL FUND", "FUND"):
        return AssetType.MUTUAL_FUND
    if normalized in ("CRYPTOCURRENCY", "CRYPTO"):
        return AssetType.CRYPTO
    if normalized in ("CURRENCY", "FX", "FOREX"):
        return AssetType.CURRENCY
    if normalized in ("FUTURE", "COMMODITY"):
        return AssetType.FUTURE
    if normalized in ("OPTION",):
        return AssetType.OPTION
    return AssetType.UNKNOWN


def _is_transient_error(exc: Exception) -> bool:
    """
    Classify whether an exception is an explicitly retryable transient failure.

    Non-retryable:
      - 429 (Rate Limit): retrying immediately makes rate limits worse.
      - 400/404: client/resource errors.
      - Domain errors (InvalidTickerError, DataNotFoundError, DataQualityError).

    Retryable:
      - Connection timeouts, ConnectionError, HTTP 502/503/504.
    """
    if isinstance(
        exc,
        (
            InvalidTickerError,
            InvalidSearchQueryError,
            DataNotFoundError,
            DataQualityError,
            ProviderRateLimitError,
        ),
    ):
        return False

    if isinstance(
        exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
    ):
        return True

    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        return status in (500, 502, 503, 504)

    return False


async def _execute_with_retry[T](
    fn: Callable[..., T],
    *args: Any,
    max_retries: int = 1,
    retry_delay_seconds: float = 2.0,
    **kwargs: Any,
) -> T:
    """
    Execute a blocking callable in a worker thread with selective transient retry.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries and _is_transient_error(exc):
                logger.warning(
                    "Transient provider failure on attempt %d/%d: %s. Retrying in %ss...",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                    retry_delay_seconds,
                )
                await asyncio.sleep(retry_delay_seconds)
                continue
            # Non-retryable or retries exhausted
            raise exc

    if last_exc is not None:
        raise last_exc
    raise ProviderError("Execution failed without exception")


class YFinanceProvider(MarketDataProvider):
    """
    Yahoo Finance market data provider implementation.
    """

    @property
    def name(self) -> str:
        return "yahoo_finance"

    async def get_quote(self, ticker: str) -> Quote:
        """
        Retrieve current quote snapshot for a ticker symbol.
        """
        normalized_ticker = validate_ticker(ticker)

        def _fetch_quote_sync() -> Quote:
            try:
                yf_ticker = yf.Ticker(normalized_ticker)
                fast_info = yf_ticker.fast_info
            except Exception as exc:
                if (
                    isinstance(exc, requests.exceptions.HTTPError)
                    and exc.response is not None
                    and exc.response.status_code == 429
                ):
                    raise ProviderRateLimitError(
                        "Rate limit exceeded on Yahoo Finance",
                        provider=self.name,
                        ticker=normalized_ticker,
                    ) from exc
                raise ProviderUnavailableError(
                    f"Failed to communicate with Yahoo Finance: {exc}",
                    provider=self.name,
                    ticker=normalized_ticker,
                ) from exc

            # Fast info resolution
            last_price = getattr(fast_info, "last_price", None)
            prev_close = getattr(fast_info, "previous_close", None)
            day_high = getattr(fast_info, "day_high", None)
            day_low = getattr(fast_info, "day_low", None)
            open_price = getattr(fast_info, "open", None)
            volume = getattr(fast_info, "last_volume", None)
            currency_str = getattr(fast_info, "currency", None) or "USD"

            # Check if fast_info returned usable quote
            if last_price is None or pd.isna(last_price):
                # Fallback to ticker.info
                try:
                    info = yf_ticker.info
                except Exception:
                    info = {}

                last_price = info.get("regularMarketPrice") or info.get("currentPrice")
                if last_price is None or pd.isna(last_price):
                    raise DataNotFoundError(
                        f"No quote data available for ticker '{normalized_ticker}'",
                        ticker=normalized_ticker,
                    )
                prev_close = info.get("regularMarketPreviousClose") or prev_close
                day_high = info.get("regularMarketDayHigh") or day_high
                day_low = info.get("regularMarketDayLow") or day_low
                open_price = info.get("regularMarketOpen") or open_price
                volume = info.get("regularMarketVolume") or volume
                currency_str = info.get("currency") or currency_str

            # Convert to domain types with Decimal
            price_dec = Decimal(str(last_price))
            prev_close_dec = (
                Decimal(str(prev_close))
                if prev_close is not None and not pd.isna(prev_close)
                else None
            )
            high_dec = (
                Decimal(str(day_high))
                if day_high is not None and not pd.isna(day_high)
                else None
            )
            low_dec = (
                Decimal(str(day_low))
                if day_low is not None and not pd.isna(day_low)
                else None
            )
            open_dec = (
                Decimal(str(open_price))
                if open_price is not None and not pd.isna(open_price)
                else None
            )

            # Calculate change and change_percent
            change_dec = None
            change_pct_dec = None
            if prev_close_dec is not None and prev_close_dec != Decimal("0"):
                change_dec = price_dec - prev_close_dec
                change_pct_dec = (change_dec / prev_close_dec) * Decimal("100")

            # Parse currency
            try:
                currency = Currency(currency_str.upper())
            except ValueError:
                currency = Currency.UNKNOWN

            # Volume as whole-share integer
            volume_int = (
                int(volume) if volume is not None and not pd.isna(volume) else None
            )

            quote = Quote(
                ticker=normalized_ticker,
                price=price_dec,
                timestamp=datetime.now(UTC),
                currency=currency,
                change=change_dec,
                change_percent=change_pct_dec,
                volume=volume_int,
                open=open_dec,
                high=high_dec,
                low=low_dec,
                previous_close=prev_close_dec,
                market_state=MarketState.REGULAR,
                provider=self.name,
                is_delayed=True,
            )
            validate_quote(quote)
            return quote

        return await _execute_with_retry(_fetch_quote_sync)

    async def get_historical_bars(
        self,
        ticker: str,
        start: date,
        end: date,
        interval: MarketInterval = MarketInterval.DAILY,
    ) -> OHLCVSeries:
        """
        Retrieve historical OHLCV daily bars for a ticker over [start, end].
        """
        normalized_ticker = validate_ticker(ticker)

        if interval != MarketInterval.DAILY:
            raise ProviderError(
                f"Interval '{interval}' is not supported in Milestone 1. Supported: {MarketInterval.DAILY.value}",
                provider=self.name,
                ticker=normalized_ticker,
            )

        if start > end:
            raise DataQualityError(
                f"Start date ({start}) cannot be after end date ({end})",
                check="start_date_lte_end_date",
                ticker=normalized_ticker,
            )

        def _fetch_history_sync() -> OHLCVSeries:
            try:
                yf_ticker = yf.Ticker(normalized_ticker)
                # Note on yfinance date range:
                # `end` parameter in yfinance history() is exclusive.
                # To include `end` date, we supply `end + 1 day`.
                end_exclusive = end + timedelta(days=1)
                df = yf_ticker.history(
                    start=start.isoformat(),
                    end=end_exclusive.isoformat(),
                    interval="1d",
                    auto_adjust=False,  # Keep raw OHLC and separate Adj Close
                )
            except Exception as exc:
                if (
                    isinstance(exc, requests.exceptions.HTTPError)
                    and exc.response is not None
                    and exc.response.status_code == 429
                ):
                    raise ProviderRateLimitError(
                        "Rate limit exceeded on Yahoo Finance",
                        provider=self.name,
                        ticker=normalized_ticker,
                    ) from exc
                raise ProviderUnavailableError(
                    f"Failed to fetch historical data from Yahoo Finance: {exc}",
                    provider=self.name,
                    ticker=normalized_ticker,
                ) from exc

            return self.normalize_dataframe(df, normalized_ticker, start, end)

        return await _execute_with_retry(_fetch_history_sync)

    def normalize_dataframe(
        self,
        df: pd.DataFrame,
        ticker: str,
        start: date,
        end: date,
    ) -> OHLCVSeries:
        """
        Normalize a raw pandas DataFrame from yfinance into an OHLCVSeries.
        """
        if df is None or df.empty:
            raise DataNotFoundError(
                f"No historical data returned for ticker '{ticker}' between {start} and {end}",
                ticker=ticker,
            )

        # Check required columns
        required_cols = {"Open", "High", "Low", "Close", "Volume"}
        missing = required_cols - set(df.columns)
        if missing:
            raise DataQualityError(
                f"Missing required columns in provider DataFrame: {missing}",
                check="required_columns",
                ticker=ticker,
            )

        has_adj_close = "Adj Close" in df.columns
        bars: list[OHLCVBar] = []

        for idx, row in df.iterrows():
            # Date index conversion
            if hasattr(idx, "date"):
                bar_date = idx.date()  # type: ignore[union-attr]
            else:
                bar_date = pd.to_datetime(idx).date()

            # Filter bounds strictly
            if bar_date < start or bar_date > end:
                continue

            # Check NaNs
            if (
                pd.isna(row["Open"])
                or pd.isna(row["High"])
                or pd.isna(row["Low"])
                or pd.isna(row["Close"])
            ):
                continue

            open_dec = Decimal(str(row["Open"]))
            high_dec = Decimal(str(row["High"]))
            low_dec = Decimal(str(row["Low"]))
            close_dec = Decimal(str(row["Close"]))
            vol_val = row["Volume"]
            volume_int = int(vol_val) if not pd.isna(vol_val) else 0

            adj_close_dec = None
            if has_adj_close and not pd.isna(row["Adj Close"]):
                adj_close_dec = Decimal(str(row["Adj Close"]))

            bar = OHLCVBar(
                timestamp=bar_date,
                open=open_dec,
                high=high_dec,
                low=low_dec,
                close=close_dec,
                volume=volume_int,
                adj_close=adj_close_dec,
            )
            bars.append(bar)

        if not bars:
            raise DataNotFoundError(
                f"No historical bars within requested date range {start} to {end} for ticker '{ticker}'",
                ticker=ticker,
            )

        series = OHLCVSeries(
            ticker=ticker,
            interval=MarketInterval.DAILY,
            bars=bars,
            provider=self.name,
            is_adjusted=has_adj_close,
        )
        validate_ohlcv_series(series)
        return series

    async def get_security(self, ticker: str) -> Security:
        """
        Retrieve security metadata for a ticker symbol.

        Populates provider-facing listing context (exchange, exchange_display,
        currency, timezone) along with security identity and asset classification.
        Missing currency is never defaulted to USD; unknown values remain UNKNOWN.
        Sector and industry are provider-supplied classifications, not authoritative GICS.
        """
        normalized_ticker = validate_ticker(ticker)

        def _fetch_security_sync() -> Security:
            try:
                yf_ticker = yf.Ticker(normalized_ticker)
                info = yf_ticker.info
            except Exception as exc:
                if (
                    isinstance(exc, requests.exceptions.HTTPError)
                    and exc.response is not None
                    and exc.response.status_code == 429
                ):
                    raise ProviderRateLimitError(
                        "Rate limit exceeded on Yahoo Finance",
                        provider=self.name,
                        ticker=normalized_ticker,
                    ) from exc
                raise ProviderUnavailableError(
                    f"Failed to fetch security metadata: {exc}",
                    provider=self.name,
                    ticker=normalized_ticker,
                ) from exc

            if not info or (
                "shortName" not in info
                and "longName" not in info
                and "symbol" not in info
            ):
                raise DataNotFoundError(
                    f"Security metadata not found for ticker '{normalized_ticker}'",
                    ticker=normalized_ticker,
                )

            name = (
                info.get("longName") or info.get("shortName") or normalized_ticker
            ).strip()
            raw_type = info.get("quoteType") or info.get("typeDisp")
            asset_type = _map_quote_type(raw_type)

            raw_currency = info.get("currency")
            currency = Currency.UNKNOWN
            if raw_currency and isinstance(raw_currency, str):
                try:
                    currency = Currency(raw_currency.strip().upper())
                except ValueError:
                    currency = Currency.UNKNOWN

            exchange = info.get("exchange")
            exchange_display = info.get("fullExchangeName") or exchange
            timezone = info.get("timeZoneFullName") or info.get("exchangeTimezoneName")

            return Security(
                ticker=normalized_ticker,
                name=name,
                asset_type=asset_type,
                currency=currency,
                exchange=str(exchange).strip() if exchange else None,
                exchange_display=(
                    str(exchange_display).strip() if exchange_display else None
                ),
                timezone=str(timezone).strip() if timezone else None,
                country=str(info["country"]).strip() if info.get("country") else None,
                sector=str(info["sector"]).strip() if info.get("sector") else None,
                industry=(
                    str(info["industry"]).strip() if info.get("industry") else None
                ),
                provider=self.name,
                fetched_at=datetime.now(UTC),
            )

        return await _execute_with_retry(_fetch_security_sync)

    async def search_securities(
        self, query: str, limit: int = 10
    ) -> list[SecuritySearchResult]:
        """
        Search for securities matching query via yfinance Search API.

        Normalizes results into domain SecuritySearchResult models.
        If provider search yields no results but the query is a valid ticker format,
        attempts direct fallback lookup via get_security.
        Sector and industry are documented as provider-supplied classifications.
        """
        cleaned_query = validate_search_query(query)
        clamped_limit = max(1, min(limit, 50))

        def _search_sync() -> list[SecuritySearchResult]:
            try:
                search_obj = yf.Search(cleaned_query, max_results=clamped_limit)
                raw_quotes = getattr(search_obj, "quotes", []) or []
            except Exception as exc:
                if (
                    isinstance(exc, requests.exceptions.HTTPError)
                    and exc.response is not None
                    and exc.response.status_code == 429
                ):
                    raise ProviderRateLimitError(
                        "Rate limit exceeded on Yahoo Finance Search",
                        provider=self.name,
                    ) from exc
                raise ProviderUnavailableError(
                    f"Failed to execute search query on Yahoo Finance: {exc}",
                    provider=self.name,
                ) from exc

            results: list[SecuritySearchResult] = []
            for q in raw_quotes:
                if not isinstance(q, dict):
                    continue
                symbol = q.get("symbol")
                if not symbol or not isinstance(symbol, str):
                    continue
                name = q.get("shortname") or q.get("longname") or symbol
                raw_type = q.get("typeDisp") or q.get("quoteType")
                asset_type = _map_quote_type(raw_type)
                exchange = q.get("exchange")
                exchange_disp = q.get("exchDisp") or exchange

                currency = None
                raw_curr = q.get("currency")
                if raw_curr and isinstance(raw_curr, str):
                    try:
                        currency = Currency(raw_curr.strip().upper())
                    except ValueError:
                        currency = Currency.UNKNOWN

                results.append(
                    SecuritySearchResult(
                        ticker=symbol.strip().upper(),
                        name=str(name).strip(),
                        asset_type=asset_type,
                        exchange=str(exchange).strip() if exchange else None,
                        exchange_display=(
                            str(exchange_disp).strip() if exchange_disp else None
                        ),
                        currency=currency,
                        provider=self.name,
                    )
                )

            return results

        results = await _execute_with_retry(_search_sync)

        # Fallback: if search yielded no results, check if the input is a valid direct ticker
        if not results:
            try:
                valid_ticker = validate_ticker(cleaned_query)
                sec = await self.get_security(valid_ticker)
                results.append(
                    SecuritySearchResult(
                        ticker=sec.ticker,
                        name=sec.name,
                        asset_type=sec.asset_type,
                        exchange=sec.exchange,
                        exchange_display=sec.exchange_display,
                        currency=sec.currency,
                        provider=self.name,
                    )
                )
            except (InvalidTickerError, DataNotFoundError, ProviderError):
                pass

        return results

    async def get_company_profile(self, ticker: str) -> CompanyProfile | None:
        """
        Retrieve corporate identity, sector, industry, and description for an equity.

        Non-corporate instruments (ETFs, Indices, Crypto, Currencies, Futures)
        return None cleanly, which is valid domain behavior and NOT an error.
        Sector and industry are provider-supplied classifications, not authoritative GICS.
        """
        normalized_ticker = validate_ticker(ticker)

        def _fetch_profile_sync() -> CompanyProfile | None:
            try:
                yf_ticker = yf.Ticker(normalized_ticker)
                info = yf_ticker.info
            except Exception as exc:
                if (
                    isinstance(exc, requests.exceptions.HTTPError)
                    and exc.response is not None
                    and exc.response.status_code == 429
                ):
                    raise ProviderRateLimitError(
                        "Rate limit exceeded on Yahoo Finance",
                        provider=self.name,
                        ticker=normalized_ticker,
                    ) from exc
                raise ProviderUnavailableError(
                    f"Failed to fetch company profile: {exc}",
                    provider=self.name,
                    ticker=normalized_ticker,
                ) from exc

            if not info:
                return None

            # Check instrument classification: non-corporate assets return None cleanly
            raw_type = info.get("quoteType") or info.get("typeDisp")
            asset_type = _map_quote_type(raw_type)
            if asset_type in (
                AssetType.INDEX,
                AssetType.ETF,
                AssetType.MUTUAL_FUND,
                AssetType.CRYPTO,
                AssetType.CURRENCY,
                AssetType.FUTURE,
                AssetType.OPTION,
            ):
                return None

            description = info.get("longBusinessSummary")
            sector = info.get("sector")
            industry = info.get("industry")
            website = info.get("website")
            country = info.get("country")
            city = info.get("city")
            state = info.get("state")
            address = info.get("address1")
            raw_employees = info.get("fullTimeEmployees")

            # If none of the corporate identity fields are present, this is not a corporate profile
            if not any([description, sector, industry, website, country, address]):
                return None

            employees: int | None = None
            if raw_employees is not None:
                try:
                    emp_int = int(raw_employees)
                    if emp_int >= 0:
                        employees = emp_int
                except (ValueError, TypeError):
                    employees = None

            name = (
                info.get("longName") or info.get("shortName") or normalized_ticker
            ).strip()

            profile = CompanyProfile(
                lookup_ticker=normalized_ticker,
                company_name=name,
                legal_name=None,
                description=str(description).strip() if description else None,
                sector=str(sector).strip() if sector else None,
                industry=str(industry).strip() if industry else None,
                website=str(website).strip() if website else None,
                country=str(country).strip() if country else None,
                city=str(city).strip() if city else None,
                state=str(state).strip() if state else None,
                address=str(address).strip() if address else None,
                employees=employees,
                provider=self.name,
                fetched_at=datetime.now(UTC),
            )
            validate_company_profile(profile)
            return profile

        return await _execute_with_retry(_fetch_profile_sync)
