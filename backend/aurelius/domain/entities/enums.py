"""
aurelius.domain.entities.enums
==============================
Domain-level enumerations for AURELIUS market data entities.

These enums represent standard types and classifications across market data
providers and ensure type safety throughout the system.
"""

from enum import StrEnum


class AssetType(StrEnum):
    """
    Classification of financial instruments.
    """

    EQUITY = "EQUITY"
    ETF = "ETF"
    INDEX = "INDEX"
    MUTUAL_FUND = "MUTUAL_FUND"
    CRYPTO = "CRYPTO"
    CURRENCY = "CURRENCY"
    UNKNOWN = "UNKNOWN"


class Currency(StrEnum):
    """
    Standard ISO-4217 currency codes supported across market data feeds.
    """

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"
    CHF = "CHF"
    INR = "INR"
    UNKNOWN = "UNKNOWN"


class MarketInterval(StrEnum):
    """
    Time aggregation interval for historical market bars (OHLCV).

    Milestone 1 Scope Restriction:
    Explicitly restricted to daily bars ('1d'). Multi-period intervals (1wk, 1mo, etc.)
    require dedicated normalization, holiday handling, and test suites, which are
    deferred to subsequent milestones.
    """

    DAILY = "1d"


class MarketState(StrEnum):
    """
    Trading session phase for a security or exchange.
    """

    PRE = "PRE"
    REGULAR = "REGULAR"
    POST = "POST"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"
