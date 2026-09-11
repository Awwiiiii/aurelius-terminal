"""
tests/unit/domain/test_errors.py
=================================
Unit tests for the domain error hierarchy.

These tests verify:
  1. Exception hierarchy (inheritance relationships)
  2. Attribute storage (provider, ticker, formula, check)
  3. String representation

These tests require NO network access, NO database, NO FastAPI server.
They are purely in-process Python tests.

Financial relevance:
  Error classification matters in a financial system.
  A ProviderRateLimitError should trigger back-off logic.
  A DataQualityError should trigger a data-quality alert.
  A CalculationError should NEVER silently return 0 or NaN.
  These tests ensure the error types exist and carry the expected context.
"""

import pytest

from aurelius.domain.errors import (
    AureliusError,
    CalculationError,
    DataNotFoundError,
    DataQualityError,
    InvalidTickerError,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)


class TestErrorHierarchy:
    """Verify the exception inheritance hierarchy."""

    def test_provider_error_is_aurelius_error(self) -> None:
        assert issubclass(ProviderError, AureliusError)

    def test_rate_limit_is_provider_error(self) -> None:
        assert issubclass(ProviderRateLimitError, ProviderError)

    def test_unavailable_is_provider_error(self) -> None:
        assert issubclass(ProviderUnavailableError, ProviderError)

    def test_data_not_found_is_aurelius_error(self) -> None:
        assert issubclass(DataNotFoundError, AureliusError)

    def test_invalid_ticker_is_aurelius_error(self) -> None:
        assert issubclass(InvalidTickerError, AureliusError)

    def test_data_quality_is_aurelius_error(self) -> None:
        assert issubclass(DataQualityError, AureliusError)

    def test_calculation_error_is_aurelius_error(self) -> None:
        assert issubclass(CalculationError, AureliusError)


class TestProviderError:
    """Verify ProviderError carries the expected attributes."""

    def test_stores_provider_and_ticker(self) -> None:
        exc = ProviderError(
            message="Connection refused",
            provider="yahoo_finance",
            ticker="AAPL",
        )
        assert exc.provider == "yahoo_finance"
        assert exc.ticker == "AAPL"
        assert exc.message == "Connection refused"

    def test_provider_and_ticker_optional(self) -> None:
        exc = ProviderError(message="Unknown error")
        assert exc.provider is None
        assert exc.ticker is None

    def test_is_catchable_as_exception(self) -> None:
        with pytest.raises(AureliusError):
            raise ProviderRateLimitError(
                message="Rate limit exceeded",
                provider="alpha_vantage",
            )


class TestCalculationError:
    """
    Verify CalculationError carries formula context.

    Financial significance:
      When a calculation fails, we must know WHICH formula failed.
      Without this, debugging return/volatility/ratio errors in production
      is extremely difficult.
    """

    def test_stores_formula_name(self) -> None:
        exc = CalculationError(
            message="Empty price series",
            formula="annualized_volatility",
        )
        assert exc.formula == "annualized_volatility"
        assert exc.message == "Empty price series"

    def test_formula_optional(self) -> None:
        exc = CalculationError(message="Division by zero")
        assert exc.formula is None


class TestDataQualityError:
    """
    Verify DataQualityError carries the failed check name.

    Financial significance:
      Knowing which quality check failed (e.g., "ohlc_consistency" vs
      "timestamp_monotonicity") is critical for diagnosing data pipeline issues.
    """

    def test_stores_check_name(self) -> None:
        exc = DataQualityError(
            message="low > high in OHLCV bar",
            check="ohlc_consistency",
            ticker="TSLA",
        )
        assert exc.check == "ohlc_consistency"
        assert exc.ticker == "TSLA"
