"""
aurelius.api.v1.schemas.quantitative
====================================
Pydantic response models for quantitative analytics endpoints:
  - Return distribution summaries and frequency histograms
  - Pairwise correlation and multi-asset correlation matrices
  - Rolling quantitative time series

Serialization Standard:
  - All numerical values (means, variances, percentiles, correlations) are serialized
    as strings to preserve exact decimal precision over JSON to web clients.
"""

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.quantitative import (
    DescriptiveStatistics,
    HistogramBin,
    MultiAssetCorrelationMatrix,
    PairwiseCorrelation,
    QuantileDistribution,
    ReturnDistributionSummary,
    RollingQuantitativeSeries,
    RollingStatisticPoint,
)


class DescriptiveStatisticsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_size: int = Field(..., description="Number of observations (N).")
    mean: str = Field(..., description="Sample mean.")
    median: str = Field(..., description="Median observation.")
    sample_variance: str | None = Field(
        default=None,
        description="Unbiased sample variance (N - 1 denominator). None if N < 2.",
    )
    population_variance: str = Field(
        ..., description="Population variance (N denominator)."
    )
    sample_std_dev: str | None = Field(
        default=None, description="Sample standard deviation. None if N < 2."
    )
    population_std_dev: str = Field(..., description="Population standard deviation.")
    min_value: str = Field(..., description="Minimum observation.")
    max_value: str = Field(..., description="Maximum observation.")
    range_value: str = Field(..., description="Total range.")
    mad: str = Field(..., description="Mean Absolute Deviation.")
    iqr: str = Field(..., description="Interquartile Range.")
    skewness: str | None = Field(
        default=None, description="Fisher-Pearson sample skewness. None if N < 3."
    )
    excess_kurtosis: str | None = Field(
        default=None, description="Sample excess kurtosis. None if N < 4."
    )

    @classmethod
    def from_domain(
        cls, entity: DescriptiveStatistics
    ) -> "DescriptiveStatisticsResponse":
        return cls(
            sample_size=entity.sample_size,
            mean=str(entity.mean),
            median=str(entity.median),
            sample_variance=str(entity.sample_variance)
            if entity.sample_variance is not None
            else None,
            population_variance=str(entity.population_variance),
            sample_std_dev=str(entity.sample_std_dev)
            if entity.sample_std_dev is not None
            else None,
            population_std_dev=str(entity.population_std_dev),
            min_value=str(entity.min_value),
            max_value=str(entity.max_value),
            range_value=str(entity.range_value),
            mad=str(entity.mad),
            iqr=str(entity.iqr),
            skewness=str(entity.skewness) if entity.skewness is not None else None,
            excess_kurtosis=str(entity.excess_kurtosis)
            if entity.excess_kurtosis is not None
            else None,
        )


class QuantileDistributionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    p1: str
    p5: str
    p10: str
    p25: str
    p50: str
    p75: str
    p90: str
    p95: str
    p99: str

    @classmethod
    def from_domain(
        cls, entity: QuantileDistribution
    ) -> "QuantileDistributionResponse":
        return cls(
            p1=str(entity.p1),
            p5=str(entity.p5),
            p10=str(entity.p10),
            p25=str(entity.p25),
            p50=str(entity.p50),
            p75=str(entity.p75),
            p90=str(entity.p90),
            p95=str(entity.p95),
            p99=str(entity.p99),
        )


class HistogramBinResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    bin_start: str
    bin_end: str
    bin_mid: str
    count: int
    frequency: str

    @classmethod
    def from_domain(cls, entity: HistogramBin) -> "HistogramBinResponse":
        return cls(
            bin_start=str(entity.bin_start),
            bin_end=str(entity.bin_end),
            bin_mid=str(entity.bin_mid),
            count=entity.count,
            frequency=str(entity.frequency),
        )


class ReturnDistributionSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str
    horizon: str
    return_type: str
    sample_size: int
    positive_count: int
    positive_pct: str
    negative_count: int
    negative_pct: str
    zero_count: int
    zero_pct: str
    statistics: DescriptiveStatisticsResponse
    quantiles: QuantileDistributionResponse
    histogram: list[HistogramBinResponse]

    @classmethod
    def from_domain(
        cls, entity: ReturnDistributionSummary
    ) -> "ReturnDistributionSummaryResponse":
        return cls(
            ticker=entity.ticker,
            horizon=entity.horizon,
            return_type=entity.return_type,
            sample_size=entity.sample_size,
            positive_count=entity.positive_count,
            positive_pct=str(entity.positive_pct),
            negative_count=entity.negative_count,
            negative_pct=str(entity.negative_pct),
            zero_count=entity.zero_count,
            zero_pct=str(entity.zero_pct),
            statistics=DescriptiveStatisticsResponse.from_domain(entity.statistics),
            quantiles=QuantileDistributionResponse.from_domain(entity.quantiles),
            histogram=[HistogramBinResponse.from_domain(b) for b in entity.histogram],
        )


class PairwiseCorrelationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker_a: str
    ticker_b: str
    matched_observations: int
    start_date: str
    end_date: str
    sample_covariance: str | None
    population_covariance: str | None
    correlation: str | None
    beta_a_to_b: str | None
    tracking_error: str | None
    is_degenerate: bool

    @classmethod
    def from_domain(cls, entity: PairwiseCorrelation) -> "PairwiseCorrelationResponse":
        return cls(
            ticker_a=entity.ticker_a,
            ticker_b=entity.ticker_b,
            matched_observations=entity.matched_observations,
            start_date=entity.start_date.isoformat(),
            end_date=entity.end_date.isoformat(),
            sample_covariance=str(entity.sample_covariance)
            if entity.sample_covariance is not None
            else None,
            population_covariance=str(entity.population_covariance)
            if entity.population_covariance is not None
            else None,
            correlation=str(entity.correlation)
            if entity.correlation is not None
            else None,
            beta_a_to_b=str(entity.beta_a_to_b)
            if entity.beta_a_to_b is not None
            else None,
            tracking_error=str(entity.tracking_error)
            if entity.tracking_error is not None
            else None,
            is_degenerate=entity.is_degenerate,
        )


class MultiAssetCorrelationMatrixResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    tickers: list[str]
    horizon: str
    common_dates_count: int
    start_date: str
    end_date: str
    correlation_matrix: list[list[str | None]]
    covariance_matrix: list[list[str | None]]

    @classmethod
    def from_domain(
        cls, entity: MultiAssetCorrelationMatrix
    ) -> "MultiAssetCorrelationMatrixResponse":
        corr_str: list[list[str | None]] = [
            [str(val) if val is not None else None for val in row]
            for row in entity.correlation_matrix
        ]
        cov_str: list[list[str | None]] = [
            [str(val) if val is not None else None for val in row]
            for row in entity.covariance_matrix
        ]
        return cls(
            tickers=entity.tickers,
            horizon=entity.horizon,
            common_dates_count=entity.common_dates_count,
            start_date=entity.start_date.isoformat(),
            end_date=entity.end_date.isoformat(),
            correlation_matrix=corr_str,
            covariance_matrix=cov_str,
        )


class RollingStatisticPointResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: str
    value: str | None

    @classmethod
    def from_domain(
        cls, entity: RollingStatisticPoint
    ) -> "RollingStatisticPointResponse":
        return cls(
            date=entity.date.isoformat(),
            value=str(entity.value) if entity.value is not None else None,
        )


class RollingQuantitativeSeriesResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker_a: str
    ticker_b: str | None
    metric_name: str
    window: int
    series: list[RollingStatisticPointResponse]

    @classmethod
    def from_domain(
        cls, entity: RollingQuantitativeSeries
    ) -> "RollingQuantitativeSeriesResponse":
        return cls(
            ticker_a=entity.ticker_a,
            ticker_b=entity.ticker_b,
            metric_name=entity.metric_name,
            window=entity.window,
            series=[
                RollingStatisticPointResponse.from_domain(p) for p in entity.series
            ],
        )
