"""
aurelius.domain.entities.quantitative
=====================================
Domain entities for quantitative analytics: univariate descriptive statistics,
quantile distributions, histogram frequency bins, pairwise multivariate
relationships, correlation matrices, and rolling quantitative time series.

All entities are immutable via ConfigDict(frozen=True).
"""

from datetime import date as PyDate
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DescriptiveStatistics(BaseModel):
    """
    Univariate statistical properties of an observed sample.
    """

    model_config = ConfigDict(frozen=True)

    sample_size: int = Field(
        ..., ge=0, description="Total number of valid observations (N)."
    )
    mean: Decimal = Field(..., description="Arithmetic sample mean (sum(x) / N).")
    median: Decimal = Field(..., description="Median observation (50th percentile).")
    sample_variance: Decimal | None = Field(
        default=None,
        description="Unbiased sample variance with Bessel's correction (N - 1 denominator). None if N < 2.",
    )
    population_variance: Decimal = Field(
        ...,
        description="Population variance with N denominator (reference metric).",
    )
    sample_std_dev: Decimal | None = Field(
        default=None,
        description="Sample standard deviation (sqrt(sample_variance)). None if N < 2.",
    )
    population_std_dev: Decimal = Field(
        ...,
        description="Population standard deviation (sqrt(population_variance)).",
    )
    min_value: Decimal = Field(..., description="Minimum observed value in sample.")
    max_value: Decimal = Field(..., description="Maximum observed value in sample.")
    range_value: Decimal = Field(
        ..., description="Total range (max_value - min_value)."
    )
    mad: Decimal = Field(
        ..., description="Mean Absolute Deviation from arithmetic mean."
    )
    iqr: Decimal = Field(..., description="Interquartile Range (Q75 - Q25).")
    skewness: Decimal | None = Field(
        default=None,
        description="Fisher-Pearson sample skewness (3rd standardized moment). None if N < 3 or zero variance.",
    )
    excess_kurtosis: Decimal | None = Field(
        default=None,
        description="Sample excess kurtosis relative to normal distribution (4th standardized moment). None if N < 4 or zero variance.",
    )


class QuantileDistribution(BaseModel):
    """
    Standard linear-interpolation quantile distribution.
    """

    model_config = ConfigDict(frozen=True)

    p1: Decimal = Field(..., description="1st percentile.")
    p5: Decimal = Field(..., description="5th percentile.")
    p10: Decimal = Field(..., description="10th percentile.")
    p25: Decimal = Field(..., description="25th percentile (Q1).")
    p50: Decimal = Field(..., description="50th percentile (Median / Q2).")
    p75: Decimal = Field(..., description="75th percentile (Q3).")
    p90: Decimal = Field(..., description="90th percentile.")
    p95: Decimal = Field(..., description="95th percentile.")
    p99: Decimal = Field(..., description="99th percentile.")


class HistogramBin(BaseModel):
    """
    Deterministic frequency histogram bin interval.
    """

    model_config = ConfigDict(frozen=True)

    bin_start: Decimal = Field(..., description="Lower bound of bin interval.")
    bin_end: Decimal = Field(..., description="Upper bound of bin interval.")
    bin_mid: Decimal = Field(..., description="Midpoint of bin interval.")
    count: int = Field(
        ..., ge=0, description="Number of observations falling into this bin."
    )
    frequency: Decimal = Field(
        ...,
        ge=Decimal("0.0"),
        le=Decimal("1.0"),
        description="Relative frequency (count / sample_size).",
    )


class ReturnDistributionSummary(BaseModel):
    """
    Comprehensive empirical distribution summary for an asset's returns.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Security ticker symbol.")
    horizon: str = Field(..., description="Historical horizon analyzed.")
    return_type: Literal["SIMPLE", "LOG"] = Field(
        ..., description="Return calculation methodology used."
    )
    sample_size: int = Field(
        ..., ge=0, description="Total number of return observations."
    )
    positive_count: int = Field(..., ge=0, description="Count of return sessions > 0.")
    positive_pct: Decimal = Field(
        ..., description="Proportion of positive return sessions."
    )
    negative_count: int = Field(..., ge=0, description="Count of return sessions < 0.")
    negative_pct: Decimal = Field(
        ..., description="Proportion of negative return sessions."
    )
    zero_count: int = Field(..., ge=0, description="Count of return sessions == 0.")
    zero_pct: Decimal = Field(..., description="Proportion of zero return sessions.")
    statistics: DescriptiveStatistics = Field(
        ..., description="Univariate summary moments and dispersion metrics."
    )
    quantiles: QuantileDistribution = Field(
        ..., description="Empirical quantile ladder."
    )
    histogram: list[HistogramBin] = Field(
        ..., description="Deterministic Freedman-Diaconis frequency histogram bins."
    )


class PairwiseCorrelation(BaseModel):
    """
    Pairwise joint statistics between two synchronous return series.
    """

    model_config = ConfigDict(frozen=True)

    ticker_a: str = Field(..., description="Primary ticker symbol.")
    ticker_b: str = Field(..., description="Secondary / benchmark ticker symbol.")
    matched_observations: int = Field(
        ..., ge=0, description="Number of synchronously matched calendar trading dates."
    )
    start_date: PyDate = Field(..., description="First common trading session date.")
    end_date: PyDate = Field(..., description="Final common trading session date.")
    sample_covariance: Decimal | None = Field(
        default=None,
        description="Sample covariance with K - 1 denominator. None if K < 2.",
    )
    population_covariance: Decimal | None = Field(
        default=None, description="Population covariance with K denominator."
    )
    correlation: Decimal | None = Field(
        default=None,
        description="Pearson correlation coefficient in [-1.0, 1.0]. None if zero variance or K < 2.",
    )
    beta_a_to_b: Decimal | None = Field(
        default=None,
        description="Market beta of ticker A relative to ticker B (Cov(A, B) / Var(B)).",
    )
    tracking_error: Decimal | None = Field(
        default=None,
        description="Annualized sample standard deviation of active daily returns (A - B).",
    )
    is_degenerate: bool = Field(
        default=False,
        description="True if zero variance or fewer than 2 matched sessions prevented valid correlation calculation.",
    )


class MultiAssetCorrelationMatrix(BaseModel):
    """
    Symmetric pairwise correlation and covariance matrices for a universe of tickers.
    """

    model_config = ConfigDict(frozen=True)

    tickers: list[str] = Field(..., description="List of tickers in matrix order.")
    horizon: str = Field(..., description="Historical time horizon analyzed.")
    common_dates_count: int = Field(
        ...,
        ge=0,
        description="Count of joint trading sessions common to all universe tickers.",
    )
    start_date: PyDate = Field(..., description="Earliest common trading session date.")
    end_date: PyDate = Field(..., description="Latest common trading session date.")
    correlation_matrix: list[list[Decimal | None]] = Field(
        ..., description="Pairwise Pearson correlation matrix."
    )
    covariance_matrix: list[list[Decimal | None]] = Field(
        ..., description="Pairwise sample covariance matrix."
    )


class RollingStatisticPoint(BaseModel):
    """
    Individual chronological data point in a rolling quantitative series.
    """

    model_config = ConfigDict(frozen=True)

    date: PyDate = Field(..., description="Trading date of observation.")
    value: Decimal | None = Field(
        default=None,
        description="Computed rolling metric value, or None during warm-up.",
    )


class RollingQuantitativeSeries(BaseModel):
    """
    Sliding window quantitative time series over W return observations.
    """

    model_config = ConfigDict(frozen=True)

    ticker_a: str = Field(..., description="Primary ticker symbol.")
    ticker_b: str | None = Field(
        default=None,
        description="Secondary ticker symbol if bivariate (e.g. rolling correlation).",
    )
    metric_name: str = Field(
        ...,
        description="Quantitative metric identifier (e.g. 'ROLLING_VOL', 'ROLLING_CORR', 'ROLLING_MEAN').",
    )
    window: int = Field(
        ..., ge=2, description="Rolling window size in return observations."
    )
    series: list[RollingStatisticPoint] = Field(
        ..., description="Chronological rolling metric points."
    )
