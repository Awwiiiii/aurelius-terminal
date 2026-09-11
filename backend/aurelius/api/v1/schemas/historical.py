"""
aurelius.api.v1.schemas.historical
==================================
Pydantic response models for historical market analysis endpoints.

Financial serialization:
  - All decimal and monetary quantities are serialized as strings to avoid
    JavaScript IEEE-754 floating-point precision loss.
  - Returns, CAGR, win rate, volatilities, and drawdowns are strings.
  - Dates are ISO-8601 strings (YYYY-MM-DD).
  - Trading volume is serialized as whole-share integer (`int`).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.historical import (
    BenchmarkComparison,
    DrawdownMetrics,
    HistoricalAnalysisSummary,
    HistoricalBarPoint,
    HistoricalExtremes,
    ReturnMetrics,
    VolatilityMetrics,
)


class ReturnMetricsResponse(BaseModel):
    """Return and performance metrics schema."""

    model_config = ConfigDict(frozen=True)

    adjusted_price_return: str = Field(
        ..., description="Return on provider-adjusted close."
    )
    cagr: str | None = Field(
        default=None, description="Calendar-time CAGR for horizons >= 365 days."
    )
    mean_daily_return: str = Field(
        ..., description="Arithmetic mean of daily simple returns."
    )
    positive_days: int = Field(..., description="Count of positive trading sessions.")
    negative_days: int = Field(..., description="Count of negative trading sessions.")
    zero_days: int = Field(..., description="Count of zero-return trading sessions.")
    win_rate: str | None = Field(
        default=None, description="Positive sessions divided by non-zero sessions."
    )

    @classmethod
    def from_domain(cls, entity: ReturnMetrics) -> "ReturnMetricsResponse":
        return cls(
            adjusted_price_return=str(entity.adjusted_price_return),
            cagr=str(entity.cagr) if entity.cagr is not None else None,
            mean_daily_return=str(entity.mean_daily_return),
            positive_days=entity.positive_days,
            negative_days=entity.negative_days,
            zero_days=entity.zero_days,
            win_rate=str(entity.win_rate) if entity.win_rate is not None else None,
        )


class VolatilityMetricsResponse(BaseModel):
    """Historical realized volatility metrics schema."""

    model_config = ConfigDict(frozen=True)

    daily_volatility: str = Field(
        ..., description="Sample standard deviation of daily returns."
    )
    annualized_volatility: str = Field(
        ..., description="Annualized historical volatility (x sqrt(252))."
    )
    trading_days_assumed: int = Field(
        default=252, description="Annualization trading day factor."
    )

    @classmethod
    def from_domain(cls, entity: VolatilityMetrics) -> "VolatilityMetricsResponse":
        return cls(
            daily_volatility=str(entity.daily_volatility),
            annualized_volatility=str(entity.annualized_volatility),
            trading_days_assumed=entity.trading_days_assumed,
        )


class DrawdownMetricsResponse(BaseModel):
    """Drawdown and peak-to-trough risk metrics schema."""

    model_config = ConfigDict(frozen=True)

    max_drawdown: str = Field(
        ..., description="Maximum peak-to-trough decline (<= 0.0)."
    )
    max_drawdown_peak_date: str = Field(
        ..., description="Date of peak preceding max drawdown."
    )
    max_drawdown_trough_date: str = Field(
        ..., description="Date of max drawdown trough."
    )
    recovery_date: str | None = Field(
        default=None, description="Date on which peak was reclaimed, or null."
    )
    is_recovered: bool = Field(..., description="True if price reclaimed the peak.")
    current_drawdown: str = Field(
        ..., description="Drawdown percentage at final observation."
    )

    @classmethod
    def from_domain(cls, entity: DrawdownMetrics) -> "DrawdownMetricsResponse":
        return cls(
            max_drawdown=str(entity.max_drawdown),
            max_drawdown_peak_date=entity.max_drawdown_peak_date.isoformat(),
            max_drawdown_trough_date=entity.max_drawdown_trough_date.isoformat(),
            recovery_date=entity.recovery_date.isoformat()
            if entity.recovery_date
            else None,
            is_recovered=entity.is_recovered,
            current_drawdown=str(entity.current_drawdown),
        )


class HistoricalExtremesResponse(BaseModel):
    """Period extremes and distances on raw Close schema."""

    model_config = ConfigDict(frozen=True)

    period_high: str = Field(..., description="Highest raw closing price.")
    period_high_date: str = Field(..., description="Date of highest raw close.")
    period_low: str = Field(..., description="Lowest raw closing price.")
    period_low_date: str = Field(..., description="Date of lowest raw close.")
    distance_from_high: str = Field(
        ..., description="Percentage distance from high to last close (<= 0%)."
    )
    distance_from_low: str = Field(
        ..., description="Percentage distance from low to last close (>= 0%)."
    )

    @classmethod
    def from_domain(cls, entity: HistoricalExtremes) -> "HistoricalExtremesResponse":
        return cls(
            period_high=str(entity.period_high),
            period_high_date=entity.period_high_date.isoformat(),
            period_low=str(entity.period_low),
            period_low_date=entity.period_low_date.isoformat(),
            distance_from_high=str(entity.distance_from_high),
            distance_from_low=str(entity.distance_from_low),
        )


class BenchmarkComparisonResponse(BaseModel):
    """Benchmark comparative performance schema."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str = Field(..., description="Benchmark identifier (e.g. SP500).")
    benchmark_name: str = Field(..., description="Descriptive benchmark name.")
    common_base_date: str = Field(
        ..., description="Earliest matched date used as 100.0 rebase point."
    )
    security_return: str = Field(
        ..., description="Security return over matched window."
    )
    benchmark_return: str = Field(
        ..., description="Benchmark return over matched window."
    )
    excess_return: str = Field(
        ..., description="Security return minus benchmark return."
    )
    correlation: str = Field(
        ..., description="Pearson correlation between daily returns."
    )

    @classmethod
    def from_domain(cls, entity: BenchmarkComparison) -> "BenchmarkComparisonResponse":
        return cls(
            benchmark_id=entity.benchmark_id,
            benchmark_name=entity.benchmark_name,
            common_base_date=entity.common_base_date.isoformat(),
            security_return=str(entity.security_return),
            benchmark_return=str(entity.benchmark_return),
            excess_return=str(entity.excess_return),
            correlation=str(entity.correlation),
        )


class HistoricalBarPointResponse(BaseModel):
    """Historical bar point time series item schema."""

    model_config = ConfigDict(frozen=True)

    date: str = Field(..., description="Session date (YYYY-MM-DD).")
    open: str = Field(..., description="Raw execution open.")
    high: str = Field(..., description="Raw execution high.")
    low: str = Field(..., description="Raw execution low.")
    close: str = Field(..., description="Raw execution close.")
    adj_close: str = Field(..., description="Provider-adjusted close.")
    volume: int = Field(..., description="Whole-share trading volume.")
    daily_return: str | None = Field(
        default=None, description="Simple daily return on adj_close."
    )
    cumulative_return: str = Field(..., description="Cumulative return from base date.")
    drawdown: str = Field(..., description="Drawdown from running peak on adj_close.")
    sma_20: str | None = Field(default=None, description="20-day SMA on raw close.")
    sma_50: str | None = Field(default=None, description="50-day SMA on raw close.")
    sma_200: str | None = Field(default=None, description="200-day SMA on raw close.")
    ema_20: str | None = Field(default=None, description="20-day EMA on raw close.")
    rolling_vol_20: str | None = Field(
        default=None, description="20-return rolling annualized volatility."
    )
    benchmark_cumulative_return: str | None = Field(
        default=None, description="Benchmark cumulative return from base date."
    )

    @classmethod
    def from_domain(cls, entity: HistoricalBarPoint) -> "HistoricalBarPointResponse":
        return cls(
            date=entity.date.isoformat(),
            open=str(entity.open),
            high=str(entity.high),
            low=str(entity.low),
            close=str(entity.close),
            adj_close=str(entity.adj_close),
            volume=entity.volume,
            daily_return=str(entity.daily_return)
            if entity.daily_return is not None
            else None,
            cumulative_return=str(entity.cumulative_return),
            drawdown=str(entity.drawdown),
            sma_20=str(entity.sma_20) if entity.sma_20 is not None else None,
            sma_50=str(entity.sma_50) if entity.sma_50 is not None else None,
            sma_200=str(entity.sma_200) if entity.sma_200 is not None else None,
            ema_20=str(entity.ema_20) if entity.ema_20 is not None else None,
            rolling_vol_20=str(entity.rolling_vol_20)
            if entity.rolling_vol_20 is not None
            else None,
            benchmark_cumulative_return=(
                str(entity.benchmark_cumulative_return)
                if entity.benchmark_cumulative_return is not None
                else None
            ),
        )


class HistoricalAnalysisResponse(BaseModel):
    """Top-level historical analysis response schema."""

    model_config = ConfigDict(frozen=True)

    ticker: str = Field(..., description="Normalized ticker symbol.")
    horizon: str = Field(..., description="Time horizon identifier (e.g. '1Y', 'YTD').")
    start_date: str = Field(..., description="Earliest session date in series.")
    end_date: str = Field(..., description="Latest session date in series.")
    calendar_days: int = Field(..., description="Elapsed calendar days.")
    trading_days: int = Field(..., description="Count of trading sessions.")
    returns: ReturnMetricsResponse = Field(
        ..., description="Return analytics on adj_close."
    )
    volatility: VolatilityMetricsResponse = Field(
        ..., description="Realized volatility analytics."
    )
    drawdowns: DrawdownMetricsResponse = Field(
        ..., description="Drawdown analytics on adj_close."
    )
    extremes: HistoricalExtremesResponse = Field(
        ..., description="Period extremes on raw close."
    )
    benchmark_comparison: BenchmarkComparisonResponse | None = Field(
        default=None, description="Benchmark comparative analytics."
    )
    series: list[HistoricalBarPointResponse] = Field(
        default_factory=list, description="Ordered bar points for charting."
    )
    provider: str = Field(..., description="Market data provider.")
    fetched_at: datetime = Field(
        ..., description="Timestamp of analysis generation (UTC)."
    )

    @classmethod
    def from_domain(
        cls, entity: HistoricalAnalysisSummary
    ) -> "HistoricalAnalysisResponse":
        return cls(
            ticker=entity.ticker,
            horizon=entity.horizon.value,
            start_date=entity.start_date.isoformat(),
            end_date=entity.end_date.isoformat(),
            calendar_days=entity.calendar_days,
            trading_days=entity.trading_days,
            returns=ReturnMetricsResponse.from_domain(entity.returns),
            volatility=VolatilityMetricsResponse.from_domain(entity.volatility),
            drawdowns=DrawdownMetricsResponse.from_domain(entity.drawdowns),
            extremes=HistoricalExtremesResponse.from_domain(entity.extremes),
            benchmark_comparison=(
                BenchmarkComparisonResponse.from_domain(entity.benchmark_comparison)
                if entity.benchmark_comparison
                else None
            ),
            series=[HistoricalBarPointResponse.from_domain(p) for p in entity.series],
            provider=entity.provider,
            fetched_at=entity.fetched_at,
        )
