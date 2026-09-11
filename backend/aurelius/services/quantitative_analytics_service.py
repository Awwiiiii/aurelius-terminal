"""
aurelius.services.quantitative_analytics_service
================================================
Service layer orchestration for quantitative market analytics:
  - Single-asset empirical return distribution profiles
  - Multi-asset inner date alignment and pairwise correlation/covariance matrices
  - Sliding window rolling quantitative time series
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from aurelius.domain.analytics.alignment import inner_align_date_series
from aurelius.domain.analytics.distribution import (
    calculate_freedman_diaconis_histogram,
    compute_distribution_breakdown,
)
from aurelius.domain.analytics.multivariate import compute_correlation_matrix
from aurelius.domain.analytics.quantiles import calculate_quantile_distribution
from aurelius.domain.analytics.returns import (
    calculate_log_daily_returns,
    calculate_simple_daily_returns,
)
from aurelius.domain.analytics.rolling import (
    calculate_rolling_correlation,
    calculate_rolling_mean,
    calculate_rolling_std,
)
from aurelius.domain.analytics.statistics import compute_descriptive_statistics
from aurelius.domain.entities.enums import MarketInterval
from aurelius.domain.entities.historical import HistoricalTimeHorizon
from aurelius.domain.entities.ohlcv import OHLCVBar
from aurelius.domain.entities.quantitative import (
    MultiAssetCorrelationMatrix,
    ReturnDistributionSummary,
    RollingQuantitativeSeries,
    RollingStatisticPoint,
)
from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import get_market_data_provider

logger = logging.getLogger(__name__)


def _compute_horizon_start_date(
    horizon: HistoricalTimeHorizon,
    end_date: date,
    custom_start: date | None = None,
) -> date:
    """Calculate the starting calendar date for a requested time horizon."""
    if horizon == HistoricalTimeHorizon.CUSTOM:
        return custom_start if custom_start else (end_date - timedelta(days=365))
    if horizon == HistoricalTimeHorizon.ONE_MONTH:
        return end_date - timedelta(days=30)
    if horizon == HistoricalTimeHorizon.THREE_MONTHS:
        return end_date - timedelta(days=91)
    if horizon == HistoricalTimeHorizon.SIX_MONTHS:
        return end_date - timedelta(days=182)
    if horizon == HistoricalTimeHorizon.YEAR_TO_DATE:
        return date(end_date.year, 1, 1)
    if horizon == HistoricalTimeHorizon.ONE_YEAR:
        return end_date - timedelta(days=365)
    if horizon == HistoricalTimeHorizon.THREE_YEARS:
        return end_date - timedelta(days=365 * 3)
    if horizon == HistoricalTimeHorizon.FIVE_YEARS:
        return end_date - timedelta(days=365 * 5)
    if horizon == HistoricalTimeHorizon.MAX:
        return date(1970, 1, 1)
    return end_date - timedelta(days=365)


class QuantitativeAnalyticsService:
    """
    Coordinates quantitative analytics domain mathematics, multi-series data fetching,
    and memory-cached result delivery.
    """

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._provider = provider or get_market_data_provider()
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[
            str,
            tuple[
                datetime,
                ReturnDistributionSummary
                | MultiAssetCorrelationMatrix
                | RollingQuantitativeSeries,
            ],
        ] = {}
        self._lock = asyncio.Lock()

    async def get_return_distribution(
        self,
        ticker: str,
        horizon: HistoricalTimeHorizon = HistoricalTimeHorizon.ONE_YEAR,
        return_type: Literal["SIMPLE", "LOG"] = "SIMPLE",
        custom_start: date | None = None,
        custom_end: date | None = None,
        force_refresh: bool = False,
    ) -> ReturnDistributionSummary:
        """
        Compute comprehensive empirical return distribution summary for a ticker.
        """
        sym = ticker.upper()
        cache_key = (
            f"dist:{sym}:{horizon.value}:{return_type}:{custom_start}:{custom_end}"
        )

        if not force_refresh:
            async with self._lock:
                if cache_key in self._cache:
                    cached_at, cached_val = self._cache[cache_key]
                    if (
                        datetime.now(UTC) - cached_at
                    ).total_seconds() < self._cache_ttl_seconds and isinstance(
                        cached_val, ReturnDistributionSummary
                    ):
                        return cached_val

        today = datetime.now(UTC).date()
        effective_end = custom_end if custom_end else today
        effective_start = _compute_horizon_start_date(
            horizon, effective_end, custom_start
        )

        # Buffer fetch 30 days prior to capture initial return baseline
        fetch_start = effective_start - timedelta(days=30)
        sec_series = await self._provider.get_historical_bars(
            sym, start=fetch_start, end=effective_end, interval=MarketInterval.DAILY
        )

        all_bars = sorted(sec_series.bars, key=lambda b: b.timestamp)
        if not all_bars:
            raise ValueError(f"No historical price data available for {sym}.")

        # Filter bars to horizon
        display_bars: list[OHLCVBar] = [
            b
            for b in all_bars
            if (b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp)
            >= effective_start
        ]
        if len(display_bars) < 2:
            display_bars = all_bars[-2:] if len(all_bars) >= 2 else all_bars

        adj_closes = [
            b.adj_close if b.adj_close is not None else b.close for b in display_bars
        ]

        if return_type == "LOG":
            raw_returns = calculate_log_daily_returns(adj_closes)
        else:
            raw_returns = calculate_simple_daily_returns(adj_closes)

        # Exclude initial None observation
        valid_returns = [r for r in raw_returns if r is not None]
        if not valid_returns:
            raise ValueError(f"Insufficient return observations for {sym}.")

        stats = compute_descriptive_statistics(valid_returns)
        quantiles = calculate_quantile_distribution(valid_returns)
        histogram_bins = calculate_freedman_diaconis_histogram(valid_returns)
        pos, pos_pct, neg, neg_pct, zero, zero_pct = compute_distribution_breakdown(
            valid_returns
        )

        summary = ReturnDistributionSummary(
            ticker=sym,
            horizon=horizon.value,
            return_type=return_type,
            sample_size=len(valid_returns),
            positive_count=pos,
            positive_pct=pos_pct,
            negative_count=neg,
            negative_pct=neg_pct,
            zero_count=zero,
            zero_pct=zero_pct,
            statistics=stats,
            quantiles=quantiles,
            histogram=histogram_bins,
        )

        async with self._lock:
            self._cache[cache_key] = (datetime.now(UTC), summary)
        return summary

    async def compare_assets(
        self,
        tickers: list[str],
        horizon: HistoricalTimeHorizon = HistoricalTimeHorizon.ONE_YEAR,
        custom_start: date | None = None,
        custom_end: date | None = None,
        force_refresh: bool = False,
    ) -> MultiAssetCorrelationMatrix:
        """
        Align multi-asset universe on common trading dates and compute pairwise correlation/covariance.
        """
        clean_tickers = [t.upper().strip() for t in tickers if t.strip()]
        if len(clean_tickers) < 2:
            raise ValueError("At least 2 tickers required for asset comparison.")

        sorted_tickers = sorted(clean_tickers)
        cache_key = f"compare:{':'.join(sorted_tickers)}:{horizon.value}:{custom_start}:{custom_end}"

        if not force_refresh:
            async with self._lock:
                if cache_key in self._cache:
                    cached_at, cached_val = self._cache[cache_key]
                    if (
                        datetime.now(UTC) - cached_at
                    ).total_seconds() < self._cache_ttl_seconds and isinstance(
                        cached_val, MultiAssetCorrelationMatrix
                    ):
                        return cached_val

        today = datetime.now(UTC).date()
        effective_end = custom_end if custom_end else today
        effective_start = _compute_horizon_start_date(
            horizon, effective_end, custom_start
        )
        fetch_start = effective_start - timedelta(days=30)

        # Retrieve historical bars for all tickers
        date_price_maps: dict[str, dict[date, Decimal]] = {}
        for sym in clean_tickers:
            series = await self._provider.get_historical_bars(
                sym, start=fetch_start, end=effective_end, interval=MarketInterval.DAILY
            )
            bars = sorted(series.bars, key=lambda b: b.timestamp)
            d_map: dict[date, Decimal] = {}
            for b in bars:
                b_date = (
                    b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp
                )
                if b_date >= effective_start:
                    d_map[b_date] = b.adj_close if b.adj_close is not None else b.close
            date_price_maps[sym] = d_map

        # Inner date alignment on common trading sessions
        common_dates, aligned_prices = inner_align_date_series(date_price_maps)
        if len(common_dates) < 2:
            empty_mat: list[list[Decimal | None]] = [
                [None] * len(clean_tickers) for _ in clean_tickers
            ]
            return MultiAssetCorrelationMatrix(
                tickers=clean_tickers,
                horizon=horizon.value,
                common_dates_count=0,
                start_date=effective_start,
                end_date=effective_end,
                correlation_matrix=empty_mat,
                covariance_matrix=empty_mat,
            )

        # Calculate aligned daily returns for each ticker (length K - 1)
        aligned_returns_map: dict[str, list[Decimal]] = {}
        for sym in clean_tickers:
            prices = aligned_prices[sym]
            rets = calculate_simple_daily_returns(prices)
            aligned_returns_map[sym] = [r for r in rets if r is not None]

        corr_matrix, cov_matrix = compute_correlation_matrix(
            clean_tickers, aligned_returns_map
        )

        result = MultiAssetCorrelationMatrix(
            tickers=clean_tickers,
            horizon=horizon.value,
            common_dates_count=len(common_dates),
            start_date=common_dates[0],
            end_date=common_dates[-1],
            correlation_matrix=corr_matrix,
            covariance_matrix=cov_matrix,
        )

        async with self._lock:
            self._cache[cache_key] = (datetime.now(UTC), result)
        return result

    async def get_rolling_series(
        self,
        ticker_a: str,
        ticker_b: str | None = None,
        metric: Literal["VOLATILITY", "CORRELATION", "MEAN"] = "VOLATILITY",
        window: int = 20,
        horizon: HistoricalTimeHorizon = HistoricalTimeHorizon.ONE_YEAR,
        custom_start: date | None = None,
        custom_end: date | None = None,
        force_refresh: bool = False,
    ) -> RollingQuantitativeSeries:
        """
        Compute sliding window quantitative time series over W returns.
        """
        sym_a = ticker_a.upper().strip()
        sym_b = ticker_b.upper().strip() if ticker_b else None

        cache_key = f"rolling:{sym_a}:{sym_b}:{metric}:{window}:{horizon.value}:{custom_start}:{custom_end}"
        if not force_refresh:
            async with self._lock:
                if cache_key in self._cache:
                    cached_at, cached_val = self._cache[cache_key]
                    if (
                        datetime.now(UTC) - cached_at
                    ).total_seconds() < self._cache_ttl_seconds and isinstance(
                        cached_val, RollingQuantitativeSeries
                    ):
                        return cached_val

        today = datetime.now(UTC).date()
        effective_end = custom_end if custom_end else today
        effective_start = _compute_horizon_start_date(
            horizon, effective_end, custom_start
        )

        # Buffer fetch W + 40 days prior to warm up rolling window
        buffer_days = int(window * 1.5) + 40
        fetch_start = effective_start - timedelta(days=buffer_days)

        series_a = await self._provider.get_historical_bars(
            sym_a, start=fetch_start, end=effective_end, interval=MarketInterval.DAILY
        )
        bars_a = sorted(series_a.bars, key=lambda b: b.timestamp)

        if metric == "CORRELATION":
            if not sym_b:
                raise ValueError(
                    "Secondary ticker (ticker_b) required for rolling correlation."
                )

            series_b = await self._provider.get_historical_bars(
                sym_b,
                start=fetch_start,
                end=effective_end,
                interval=MarketInterval.DAILY,
            )
            bars_b = sorted(series_b.bars, key=lambda b: b.timestamp)

            # Build date-keyed maps
            map_a = {
                (b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp): (
                    b.adj_close if b.adj_close is not None else b.close
                )
                for b in bars_a
            }
            map_b = {
                (b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp): (
                    b.adj_close if b.adj_close is not None else b.close
                )
                for b in bars_b
            }

            common_dates, aligned = inner_align_date_series(
                {sym_a: map_a, sym_b: map_b}
            )
            if len(common_dates) < window + 1:
                return RollingQuantitativeSeries(
                    ticker_a=sym_a,
                    ticker_b=sym_b,
                    metric_name=metric,
                    window=window,
                    series=[],
                )

            rets_a = [
                r
                for r in calculate_simple_daily_returns(aligned[sym_a])
                if r is not None
            ]
            rets_b = [
                r
                for r in calculate_simple_daily_returns(aligned[sym_b])
                if r is not None
            ]

            # Return dates correspond to common_dates[1:]
            return_dates = common_dates[1:]
            rolling_vals = calculate_rolling_correlation(rets_a, rets_b, window=window)

        elif metric == "MEAN":
            prices_a = [
                b.adj_close if b.adj_close is not None else b.close for b in bars_a
            ]
            rets_a = [
                r for r in calculate_simple_daily_returns(prices_a) if r is not None
            ]
            return_dates = [
                (b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp)
                for b in bars_a[1:]
            ]
            rolling_vals = calculate_rolling_mean(rets_a, window=window)

        else:  # VOLATILITY
            prices_a = [
                b.adj_close if b.adj_close is not None else b.close for b in bars_a
            ]
            rets_a = [
                r for r in calculate_simple_daily_returns(prices_a) if r is not None
            ]
            return_dates = [
                (b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp)
                for b in bars_a[1:]
            ]
            rolling_vals = calculate_rolling_std(rets_a, window=window)

        # Filter output points to effective display horizon
        points: list[RollingStatisticPoint] = []
        for d, v in zip(return_dates, rolling_vals, strict=True):
            if d >= effective_start:
                points.append(RollingStatisticPoint(date=d, value=v))

        series_res = RollingQuantitativeSeries(
            ticker_a=sym_a,
            ticker_b=sym_b,
            metric_name=metric,
            window=window,
            series=points,
        )

        async with self._lock:
            self._cache[cache_key] = (datetime.now(UTC), series_res)
        return series_res


_quantitative_service_instance: QuantitativeAnalyticsService | None = None


def get_quantitative_analytics_service() -> QuantitativeAnalyticsService:
    """Dependency injection factory for QuantitativeAnalyticsService singleton."""
    global _quantitative_service_instance
    if _quantitative_service_instance is None:
        _quantitative_service_instance = QuantitativeAnalyticsService()
    return _quantitative_service_instance
