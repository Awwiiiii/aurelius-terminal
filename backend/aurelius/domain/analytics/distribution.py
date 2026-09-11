"""
aurelius.domain.analytics.distribution
======================================
Deterministic frequency histogram binning and directional return observation breakdowns.

Methodology:
  Primary Algorithm: Freedman-Diaconis rule:
    h = 2 * IQR / n^(1/3)
    bin_count = min(50, max(5, ceil((max - min) / h)))

  Deterministic Edge-Case Fallbacks:
    - n < 4: 1 bin if constant, or 3 equal bins if min < max.
    - IQR == 0 (with s > 0): Scott's normal reference rule:
        h = 3.49 * s / n^(1/3)
    - All observations identical (max == min or s == 0):
        Exactly 1 bin spanning [min - 0.005, max + 0.005] with count = n and freq = 1.0.
    - Bins are half-open [b_k, b_{k+1}) except the final bin which is closed [b_{K-1}, b_K].
"""

import math
from decimal import ROUND_HALF_UP, Decimal

from aurelius.domain.analytics.quantiles import calculate_percentile
from aurelius.domain.analytics.statistics import calculate_sample_std_dev
from aurelius.domain.entities.quantitative import HistogramBin


def compute_distribution_breakdown(
    data: list[Decimal],
) -> tuple[int, Decimal, int, Decimal, int, Decimal]:
    """
    Compute directional observation counts and percentages:
    (positive_count, positive_pct, negative_count, negative_pct, zero_count, zero_pct).
    """
    n = len(data)
    if n == 0:
        return 0, Decimal("0.0"), 0, Decimal("0.0"), 0, Decimal("0.0")

    pos = sum(1 for x in data if x > Decimal("0.0"))
    neg = sum(1 for x in data if x < Decimal("0.0"))
    zero = sum(1 for x in data if x == Decimal("0.0"))

    dec_n = Decimal(n)
    pos_pct = (Decimal(pos) / dec_n).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    neg_pct = (Decimal(neg) / dec_n).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    zero_pct = (Decimal(zero) / dec_n).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )

    return pos, pos_pct, neg, neg_pct, zero, zero_pct


def calculate_freedman_diaconis_histogram(data: list[Decimal]) -> list[HistogramBin]:
    """
    Partition numerical observations into deterministic histogram frequency bins.
    """
    if not data:
        raise ValueError("Cannot construct histogram from empty sequence.")

    n = len(data)
    min_val = min(data)
    max_val = max(data)

    # Edge Case: All observations identical
    if min_val == max_val:
        return [
            HistogramBin(
                bin_start=(min_val - Decimal("0.005")).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP
                ),
                bin_end=(max_val + Decimal("0.005")).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP
                ),
                bin_mid=min_val.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                count=n,
                frequency=Decimal("1.000000"),
            )
        ]

    # Edge Case: Small sample n < 4
    if n < 4:
        bin_count = 3
        step = (max_val - min_val) / Decimal(bin_count)
        return _build_bins_and_count(data, min_val, max_val, bin_count, step, n)

    # Standard Freedman-Diaconis calculation
    q25 = calculate_percentile(data, 0.25)
    q75 = calculate_percentile(data, 0.75)
    iqr = q75 - q25

    n_cbrt = float(n) ** (1.0 / 3.0)
    data_range_float = float(max_val - min_val)

    if iqr > Decimal("0.0"):
        h = (2.0 * float(iqr)) / n_cbrt
        raw_bins = math.ceil(data_range_float / h) if h > 0 else 10
        bin_count = min(50, max(5, raw_bins))
    else:
        # Fallback: Scott's rule when IQR == 0
        s_std = calculate_sample_std_dev(data)
        if s_std is not None and s_std > Decimal("0.0"):
            h_scott = (3.49 * float(s_std)) / n_cbrt
            raw_bins = math.ceil(data_range_float / h_scott) if h_scott > 0 else 10
            bin_count = min(50, max(5, raw_bins))
        else:
            bin_count = 10

    step = (max_val - min_val) / Decimal(bin_count)
    return _build_bins_and_count(data, min_val, max_val, bin_count, step, n)


def _build_bins_and_count(
    data: list[Decimal],
    min_val: Decimal,
    max_val: Decimal,
    bin_count: int,
    step: Decimal,
    n: int,
) -> list[HistogramBin]:
    """Helper to partition intervals and bin count observations."""
    bin_counts = [0] * bin_count

    for x in data:
        if x >= max_val:
            bin_counts[-1] += 1
        elif x <= min_val:
            bin_counts[0] += 1
        else:
            # Fraction along range
            frac = float((x - min_val) / (max_val - min_val))
            idx = int(frac * bin_count)
            if idx >= bin_count:
                idx = bin_count - 1
            bin_counts[idx] += 1

    bins: list[HistogramBin] = []
    dec_n = Decimal(n)

    for k in range(bin_count):
        b_start = min_val + Decimal(k) * step
        b_end = min_val + Decimal(k + 1) * step if k < bin_count - 1 else max_val
        b_mid = (b_start + b_end) / Decimal("2")
        c = bin_counts[k]
        freq = (Decimal(c) / dec_n).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

        bins.append(
            HistogramBin(
                bin_start=b_start.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                bin_end=b_end.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                bin_mid=b_mid.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                count=c,
                frequency=freq,
            )
        )

    return bins
