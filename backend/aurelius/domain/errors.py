"""
aurelius.domain.errors
======================
Domain-specific exception hierarchy for AURELIUS.

Design principle:
  Exceptions are typed and informative. They carry enough context to produce
  meaningful log entries and actionable API error responses without exposing
  internal implementation details or leaking secrets.

Exception hierarchy:
  AureliusError                        # Base for all application errors
  ├── ProviderError                    # External data provider issues
  │   ├── ProviderRateLimitError       # Provider has rate-limited this client
  │   └── ProviderUnavailableError     # Provider is unreachable or returned a server error
  ├── DataNotFoundError                # Valid request, but no data exists
  ├── InvalidTickerError               # Malformed or unsupported ticker symbol
  ├── DataQualityError                 # Data failed quality/sanity checks
  └── CalculationError                 # A financial calculation produced invalid output

These exceptions are raised in the domain and infrastructure layers.
The API layer (aurelius.api) maps them to HTTP responses via FastAPI exception handlers.
"""


class AureliusError(Exception):
    """
    Base class for all AURELIUS application errors.

    All domain, provider, and calculation errors inherit from this class.
    This makes it easy to catch any AURELIUS-specific error in one place
    while still allowing granular handling of specific subtypes.
    """


# ---------------------------------------------------------------------------
# Provider errors
# ---------------------------------------------------------------------------


class ProviderError(AureliusError):
    """
    Raised when an external data provider returns an error or behaves unexpectedly.

    Subtypes distinguish between different failure modes so the API layer
    can return semantically correct HTTP status codes (503 vs 429 vs 404).

    Attributes:
        provider: Identifier of the provider that failed (e.g., "yahoo_finance").
        ticker:   The ticker symbol being requested, if applicable.
        message:  Human-readable description of the failure.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        ticker: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.ticker = ticker
        self.message = message

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"provider={self.provider!r}, "
            f"ticker={self.ticker!r}, "
            f"message={self.message!r})"
        )


class ProviderRateLimitError(ProviderError):
    """
    Raised when a provider has rate-limited this client.

    Maps to HTTP 429 Too Many Requests.

    Context:
        Different providers have very different rate limits. For example:
        - Yahoo Finance (unofficial): informal limits, not documented
        - Alpha Vantage (free tier): 25 requests/day
        - Financial Modeling Prep (free tier): 250 requests/day
        When this error is raised, callers should back off and not retry
        immediately.
    """


class ProviderUnavailableError(ProviderError):
    """
    Raised when a provider cannot be reached or returns a server error (5xx).

    Maps to HTTP 503 Service Unavailable.

    Context:
        The application should not fabricate data when a provider is unavailable.
        Surface this error explicitly so the caller knows the data is stale or absent.
    """


# ---------------------------------------------------------------------------
# Data errors
# ---------------------------------------------------------------------------


class DataNotFoundError(AureliusError):
    """
    Raised when a valid request is made for data that does not exist.

    Maps to HTTP 404 Not Found.

    Example: Requesting OHLCV data for a date range where the security was not
    yet listed or trading was suspended.

    Attributes:
        ticker:  Ticker symbol, if applicable.
        message: Description of what was not found.
    """

    def __init__(
        self,
        message: str,
        ticker: str | None = None,
    ) -> None:
        super().__init__(message)
        self.ticker = ticker
        self.message = message


class InvalidTickerError(AureliusError):
    """
    Raised when the provided ticker symbol is malformed or not supported.

    Maps to HTTP 400 Bad Request.

    Design note:
        Ticker validation is intentionally strict at the API boundary.
        This prevents garbage inputs from being sent to providers, wasting
        rate-limit budget.

    Attributes:
        ticker:  The invalid ticker string received.
        message: Description of the validation failure.
    """

    def __init__(
        self,
        message: str,
        ticker: str | None = None,
    ) -> None:
        super().__init__(message)
        self.ticker = ticker
        self.message = message


class DataQualityError(AureliusError):
    """
    Raised when data retrieved from a provider fails quality checks.

    Maps to HTTP 422 Unprocessable Entity (or 500 in extreme cases).

    Design principle:
        AURELIUS never silently returns data that has failed quality checks.
        It is better to surface a DataQualityError and explain the problem
        than to pass incorrect financial data to the user.

        Examples of triggers:
        - OHLCV bar where low > high (impossible)
        - Negative volume (invalid for most instruments)
        - Price series with unexpected multi-day gaps on trading days
        - Timestamp ordering violation (dates not monotonically increasing)

    Attributes:
        check:   Name of the quality check that failed.
        ticker:  Ticker symbol, if applicable.
        message: Description of the quality issue.
    """

    def __init__(
        self,
        message: str,
        check: str | None = None,
        ticker: str | None = None,
    ) -> None:
        super().__init__(message)
        self.check = check
        self.ticker = ticker
        self.message = message


class CalculationError(AureliusError):
    """
    Raised when a financial calculation produces an invalid or undefined result.

    Maps to HTTP 500 Internal Server Error.

    Examples:
        - Division by zero in a ratio calculation (e.g., zero revenue in P/S ratio)
        - Empty price series passed to volatility function
        - NaN or Inf produced by a numerical operation

    Design note:
        When a calculation fails, the correct response is to raise this error,
        NOT to return NaN, 0, or a fabricated value. The API layer must surface
        this clearly to the client.

    Attributes:
        formula: Name of the formula or calculation that failed (e.g., "sharpe_ratio").
        message: Description of the failure.
    """

    def __init__(
        self,
        message: str,
        formula: str | None = None,
    ) -> None:
        super().__init__(message)
        self.formula = formula
        self.message = message
