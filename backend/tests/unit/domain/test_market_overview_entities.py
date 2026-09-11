"""
tests/unit/domain/test_market_overview_entities.py
==================================================
Unit tests for Market Overview domain entities, benchmark definitions,
financial semantics (volume/market cap/VIX points), and immutability.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurelius.domain.entities import (
    CANONICAL_BENCHMARKS,
    BenchmarkCategory,
    BenchmarkDefinition,
    BenchmarkSnapshot,
    Currency,
    DataFreshness,
    MarketMoverItem,
    MarketOverviewSnapshot,
    MarketSessionState,
    MarketStatus,
    MoverCategory,
)


def test_canonical_benchmarks_registry() -> None:
    assert len(CANONICAL_BENCHMARKS) == 5
    assert set(CANONICAL_BENCHMARKS.keys()) == {
        "SP500",
        "DOW",
        "NASDAQ",
        "RUSSELL2000",
        "VIX",
    }

    sp500 = CANONICAL_BENCHMARKS["SP500"]
    assert isinstance(sp500, BenchmarkDefinition)
    assert sp500.benchmark_id == "SP500"
    assert sp500.category == BenchmarkCategory.LARGE_CAP_CORE
    assert sp500.is_currency_priced is True

    vix = CANONICAL_BENCHMARKS["VIX"]
    assert vix.benchmark_id == "VIX"
    assert vix.category == BenchmarkCategory.VOLATILITY
    assert vix.is_currency_priced is False
    assert "implied volatility" in vix.description.lower()

    # Verify immutability
    with pytest.raises(ValidationError):
        vix.name = "Modified VIX"  # type: ignore[misc]


def test_benchmark_snapshot_equity_index() -> None:
    now = datetime(2026, 9, 11, 20, 0, tzinfo=UTC)
    snap = BenchmarkSnapshot(
        benchmark_id="SP500",
        name="S&P 500 Index",
        category=BenchmarkCategory.LARGE_CAP_CORE,
        provider_ticker="^GSPC",
        price=Decimal("5600.25"),
        change=Decimal("25.50"),
        change_percent=Decimal("0.46"),
        previous_close=Decimal("5574.75"),
        day_high=Decimal("5610.00"),
        day_low=Decimal("5565.10"),
        currency=Currency.USD,
        is_currency_priced=True,
        provider="yahoo_finance",
        timestamp=now,
    )
    assert snap.price == Decimal("5600.25")
    assert snap.is_currency_priced is True
    assert snap.currency == Currency.USD

    with pytest.raises(ValidationError):
        snap.price = Decimal("5700.00")  # type: ignore[misc]


def test_benchmark_snapshot_vix_semantics() -> None:
    now = datetime(2026, 9, 11, 20, 0, tzinfo=UTC)
    vix_snap = BenchmarkSnapshot(
        benchmark_id="VIX",
        name="CBOE Volatility Index",
        category=BenchmarkCategory.VOLATILITY,
        provider_ticker="^VIX",
        price=Decimal("15.73"),
        change=Decimal("-0.82"),
        change_percent=Decimal("-4.95"),
        previous_close=Decimal("16.55"),
        currency=Currency.UNKNOWN,
        is_currency_priced=False,
        provider="yahoo_finance",
        timestamp=now,
    )
    assert vix_snap.price == Decimal("15.73")
    assert vix_snap.is_currency_priced is False
    assert vix_snap.currency == Currency.UNKNOWN


def test_market_mover_volume_and_market_cap_semantics() -> None:
    # 1. Valid volume and reported market cap
    mover1 = MarketMoverItem(
        ticker="NVDA",
        name="NVIDIA Corporation",
        price=Decimal("120.50"),
        change=Decimal("6.25"),
        change_percent=Decimal("5.47"),
        previous_close=Decimal("114.25"),
        volume=45000000,
        market_cap=Decimal("2960000000000"),
        exchange="NMS",
        category=MoverCategory.GAINERS,
    )
    assert mover1.volume == 45000000
    assert isinstance(mover1.volume, int)
    assert mover1.market_cap == Decimal("2960000000000")

    # 2. Missing volume and missing market cap: must be None, NEVER defaulted to 0
    mover2 = MarketMoverItem(
        ticker="TINY",
        name="Tiny Illiquid Corp",
        price=Decimal("3.50"),
        change=Decimal("-0.35"),
        change_percent=Decimal("-9.09"),
        volume=None,
        market_cap=None,
        category=MoverCategory.LOSERS,
    )
    assert mover2.volume is None
    assert mover2.volume != 0
    assert mover2.market_cap is None

    # 3. Explicit zero volume (verified no trades during session) is distinct from None
    mover3 = MarketMoverItem(
        ticker="HALT",
        name="Halted Corp",
        price=Decimal("10.00"),
        change=Decimal("0.00"),
        change_percent=Decimal("0.00"),
        volume=0,
        category=MoverCategory.LOSERS,
    )
    assert mover3.volume == 0
    assert mover3.volume is not None


def test_market_status_telemetry() -> None:
    status = MarketStatus(
        region="US",
        session_state=MarketSessionState.REGULAR_OPEN,
        session_message="Regular trading session active.",
        is_indicative=True,
    )
    assert status.session_state == MarketSessionState.REGULAR_OPEN
    assert status.region == "US"
    assert status.is_indicative is True

    weekend_status = MarketStatus(
        region="US",
        session_state=MarketSessionState.WEEKEND,
        session_message="Markets closed for weekend.",
    )
    assert weekend_status.session_state == MarketSessionState.WEEKEND

    unknown_status = MarketStatus(
        region="US",
        session_state=MarketSessionState.UNKNOWN,
        session_message="Session telemetry unverified.",
    )
    assert unknown_status.session_state == MarketSessionState.UNKNOWN


def test_market_overview_snapshot_cross_category_and_caching() -> None:
    now = datetime(2026, 9, 11, 20, 0, tzinfo=UTC)
    status = MarketStatus(
        region="US",
        session_state=MarketSessionState.REGULAR_OPEN,
    )
    benchmarks = [
        BenchmarkSnapshot(
            benchmark_id="SP500",
            name="S&P 500 Index",
            category=BenchmarkCategory.LARGE_CAP_CORE,
            provider_ticker="^GSPC",
            price=Decimal("5600.00"),
            change=Decimal("10.00"),
            change_percent=Decimal("0.18"),
            currency=Currency.USD,
            is_currency_priced=True,
            provider="yahoo_finance",
            timestamp=now,
        )
    ]
    # Legitimate cross-category overlap: TSLA is both a top gainer and top active
    tsla_gainer = MarketMoverItem(
        ticker="TSLA",
        name="Tesla Inc",
        price=Decimal("240.00"),
        change=Decimal("15.00"),
        change_percent=Decimal("6.67"),
        volume=80000000,
        category=MoverCategory.GAINERS,
    )
    tsla_active = MarketMoverItem(
        ticker="TSLA",
        name="Tesla Inc",
        price=Decimal("240.00"),
        change=Decimal("15.00"),
        change_percent=Decimal("6.67"),
        volume=80000000,
        category=MoverCategory.ACTIVE,
    )

    snapshot = MarketOverviewSnapshot(
        market_status=status,
        benchmarks=benchmarks,
        gainers=[tsla_gainer],
        losers=[],
        active=[tsla_active],
        fetched_at=now,
        freshness=DataFreshness.DELAYED,
        cached=False,
        provider="yahoo_finance",
    )

    assert len(snapshot.gainers) == 1
    assert len(snapshot.active) == 1
    assert snapshot.gainers[0].ticker == snapshot.active[0].ticker == "TSLA"
    assert snapshot.cached is False
