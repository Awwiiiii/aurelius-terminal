"""
Unit tests for benchmark comparison:
- Inner date alignment (filtering mismatched dates)
- Common base date designation
- Synchronized returns and excess return calculation
- Pearson correlation
"""

from datetime import datetime
from decimal import Decimal

from aurelius.domain.analytics.benchmark import align_and_compare_benchmark
from aurelius.domain.entities.ohlcv import OHLCVBar


def _make_bar(dt_str: str, close: str, adj_close: str) -> OHLCVBar:
    dt = datetime.fromisoformat(dt_str).date()
    return OHLCVBar(
        timestamp=dt,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        adj_close=Decimal(adj_close),
        volume=1000000,
    )


def test_benchmark_inner_date_alignment_and_metrics():
    # Security has bars for Jan 1, Jan 2, Jan 3, Jan 5
    sec_bars = [
        _make_bar("2023-01-01T00:00:00", "100.0", "100.0"),
        _make_bar("2023-01-02T00:00:00", "105.0", "105.0"),
        _make_bar("2023-01-03T00:00:00", "110.0", "110.0"),
        _make_bar("2023-01-05T00:00:00", "115.0", "115.0"),  # No bmk on Jan 5
    ]

    # Benchmark has bars for Dec 31 (not in sec), Jan 1, Jan 2, Jan 3, Jan 4 (not in sec)
    bmk_bars = [
        _make_bar("2022-12-31T00:00:00", "3800.0", "3800.0"),
        _make_bar("2023-01-01T00:00:00", "3900.0", "3900.0"),
        _make_bar("2023-01-02T00:00:00", "3978.0", "3978.0"),  # +2%
        _make_bar("2023-01-03T00:00:00", "4095.0", "4095.0"),  # approx +2.94%
        _make_bar("2023-01-04T00:00:00", "4100.0", "4100.0"),
    ]

    comparison, bmk_map = align_and_compare_benchmark(
        sec_bars, bmk_bars, benchmark_id="SP500", benchmark_name="S&P 500"
    )

    assert comparison is not None
    # Common dates are Jan 1, Jan 2, Jan 3
    assert str(comparison.common_base_date) == "2023-01-01"
    # Security return: 100 -> 110 = +10%
    assert comparison.security_return == Decimal("0.100000")
    # Benchmark return: 3900 -> 4095 = +5%
    assert comparison.benchmark_return == Decimal("0.050000")
    # Excess return: 10% - 5% = +5%
    assert comparison.excess_return == Decimal("0.050000")
    # Correlation between [0.05, 0.0476] and [0.02, 0.0294]
    assert comparison.correlation is not None
    assert Decimal("-1.0") <= comparison.correlation <= Decimal("1.0")

    # Matched cumulative map check
    assert len(bmk_map) == 3
    assert bmk_map[comparison.common_base_date] == Decimal("0.000000")
