"""
tests/unit/domain/analytics/test_multivariate.py
================================================
Unit tests for bivariate and multivariate statistics: sample/pop covariance,
Pearson correlation, beta, tracking error, and correlation matrix.
"""

from datetime import date
from decimal import Decimal

from aurelius.domain.analytics.multivariate import (
    calculate_market_beta,
    calculate_pearson_correlation,
    calculate_tracking_error,
    compute_correlation_matrix,
    compute_pairwise_statistics,
)


def test_dataset_d3_correlation_triad():
    """
    Validate Dataset D3:
      - Perfectly Collinear Positive (rho = +1.0000)
      - Perfectly Collinear Negative (rho = -1.0000)
      - Orthogonal / Zero Correlation (rho = 0.0000)
    """
    x = [Decimal("1.0"), Decimal("2.0"), Decimal("3.0"), Decimal("4.0")]

    # Positive: y = 2x + 1
    y_pos = [Decimal("3.0"), Decimal("5.0"), Decimal("7.0"), Decimal("9.0")]
    corr_pos = calculate_pearson_correlation(x, y_pos)
    assert corr_pos == Decimal("1.0000")

    # Negative: y = -3x
    y_neg = [Decimal("-3.0"), Decimal("-6.0"), Decimal("-9.0"), Decimal("-12.0")]
    corr_neg = calculate_pearson_correlation(x, y_neg)
    assert corr_neg == Decimal("-1.0000")

    # Orthogonal: x_orth = [1, -1, 1, -1], y_orth = [1, 1, -1, -1]
    x_orth = [Decimal("1.0"), Decimal("-1.0"), Decimal("1.0"), Decimal("-1.0")]
    y_orth = [Decimal("1.0"), Decimal("1.0"), Decimal("-1.0"), Decimal("-1.0")]
    corr_orth = calculate_pearson_correlation(x_orth, y_orth)
    assert corr_orth == Decimal("0.0000")


def test_zero_variance_degenerate_correlation():
    """If variance of one series is zero, correlation is mathematically undefined (None)."""
    x = [Decimal("1.0"), Decimal("2.0"), Decimal("3.0")]
    const_y = [Decimal("5.0"), Decimal("5.0"), Decimal("5.0")]

    assert calculate_pearson_correlation(x, const_y) is None

    dates = [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)]
    pw = compute_pairwise_statistics("A", "B", dates, x, const_y)
    assert pw.is_degenerate is True
    assert pw.correlation is None


def test_market_beta_and_tracking_error():
    # Asset returns vs Benchmark returns
    # y = 1.5 * x + epsilon
    bmk = [Decimal("0.01"), Decimal("-0.01"), Decimal("0.02"), Decimal("-0.02")]
    asset = [Decimal("0.015"), Decimal("-0.015"), Decimal("0.030"), Decimal("-0.030")]

    beta = calculate_market_beta(asset, bmk)
    assert beta == Decimal("1.5000")

    # Active diffs are 0.005, -0.005, 0.010, -0.010 -> active risk exists
    te = calculate_tracking_error(asset, bmk)
    assert te is not None
    assert te > Decimal("0.0")


def test_correlation_matrix_properties():
    tickers = ["AAPL", "MSFT"]
    returns_map = {
        "AAPL": [Decimal("0.01"), Decimal("-0.02"), Decimal("0.03"), Decimal("0.01")],
        "MSFT": [
            Decimal("0.008"),
            Decimal("-0.015"),
            Decimal("0.025"),
            Decimal("0.012"),
        ],
    }
    corr_mat, cov_mat = compute_correlation_matrix(tickers, returns_map)

    # Diagonals must be 1.0000
    assert corr_mat[0][0] == Decimal("1.0000")
    assert corr_mat[1][1] == Decimal("1.0000")

    # Symmetry
    assert corr_mat[0][1] == corr_mat[1][0]
    assert cov_mat[0][1] == cov_mat[1][0]
    assert corr_mat[0][1] is not None
    assert corr_mat[0][1] > Decimal("0.9")  # highly correlated


def test_correlation_matrix_with_degenerate_series():
    """
    For a zero-variance series, correlation is mathematically undefined.
    The matrix diagonal must NOT blindly force 1.0; it must yield None.
    """
    tickers = ["AAPL", "CONST"]
    returns_map = {
        "AAPL": [Decimal("0.01"), Decimal("-0.02"), Decimal("0.03"), Decimal("0.01")],
        "CONST": [Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")],
    }
    corr_mat, cov_mat = compute_correlation_matrix(tickers, returns_map)

    # AAPL is non-degenerate -> diagonal is 1.0000
    assert corr_mat[0][0] == Decimal("1.0000")
    # CONST is zero-variance -> diagonal is None, not 1.0000
    assert corr_mat[1][1] is None
    # Off-diagonals are None
    assert corr_mat[0][1] is None
    assert corr_mat[1][0] is None
    # Covariance with constant series is 0.00000000
    assert cov_mat[0][1] == Decimal("0.00000000")
    assert cov_mat[1][1] == Decimal("0.00000000")
