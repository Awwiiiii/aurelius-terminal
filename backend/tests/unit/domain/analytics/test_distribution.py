"""
tests/unit/domain/analytics/test_distribution.py
================================================
Unit tests for deterministic Freedman-Diaconis histogram binning and
directional return observation breakdowns.
"""

from decimal import Decimal

from aurelius.domain.analytics.distribution import (
    calculate_freedman_diaconis_histogram,
    compute_distribution_breakdown,
)


def test_freedman_diaconis_histogram_sum_conservation():
    """Verify that bin counts sum exactly to N and relative frequencies sum to 1.0."""
    data = [Decimal(str(i * 0.005 - 0.05)) for i in range(30)]
    bins = calculate_freedman_diaconis_histogram(data)

    assert len(bins) >= 5
    total_count = sum(b.count for b in bins)
    assert total_count == 30

    total_freq = sum(b.frequency for b in bins)
    assert abs(float(total_freq) - 1.0) < 1e-4

    # Contiguity check
    for i in range(len(bins) - 1):
        assert bins[i].bin_end == bins[i + 1].bin_start


def test_freedman_diaconis_fallbacks():
    # Fallback 1: Constant series (all identical) -> exactly 1 bin
    const_data = [Decimal("0.02")] * 10
    bins_const = calculate_freedman_diaconis_histogram(const_data)
    assert len(bins_const) == 1
    assert bins_const[0].count == 10
    assert bins_const[0].frequency == Decimal("1.000000")

    # Fallback 2: Small sample n = 3 -> 3 equal-width bins
    n3 = [Decimal("0.01"), Decimal("0.02"), Decimal("0.03")]
    bins_n3 = calculate_freedman_diaconis_histogram(n3)
    assert len(bins_n3) == 3
    assert sum(b.count for b in bins_n3) == 3

    # Fallback 3: Zero IQR with positive standard deviation
    zero_iqr_data = (
        [Decimal("0.0")] * 20 + [Decimal("-0.05")] * 2 + [Decimal("0.05")] * 2
    )
    bins_scott = calculate_freedman_diaconis_histogram(zero_iqr_data)
    assert len(bins_scott) >= 5
    assert sum(b.count for b in bins_scott) == len(zero_iqr_data)


def test_distribution_breakdown():
    returns = [
        Decimal("0.01"),
        Decimal("-0.02"),
        Decimal("0.0"),
        Decimal("0.03"),
        Decimal("-0.01"),
    ]
    pos, pos_pct, neg, neg_pct, zero, zero_pct = compute_distribution_breakdown(returns)

    assert pos == 2
    assert pos_pct == Decimal("0.4000")
    assert neg == 2
    assert neg_pct == Decimal("0.4000")
    assert zero == 1
    assert zero_pct == Decimal("0.2000")
