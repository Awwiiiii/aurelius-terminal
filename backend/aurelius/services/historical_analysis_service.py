"""
aurelius.services.historical_analysis_service
=============================================
Service layer orchestrating historical market data retrieval, time-horizon
resolution, indicator warm-up, pure analytics computation, benchmark
alignment, and caching.

Financial Principles:
  1. Price Series Policy:
     - Technical indicators (SMA20, SMA50, SMA200, EMA20) and period extremes
       are computed strictly on nominal raw Close prices.
     - Return series, calendar CAGR, win rate, volatility, and drawdowns are
       computed strictly on provider-adjusted Close (adj_close).
  2. Indicator Warm-Up:
     - Queries an indicator warm-up buffer (up to ~350 calendar days) prior to
       start_date so moving averages are immediately populated across the
       display window when historical depth exists.
  3. Metric Window:
     - All summary metrics (returns, volatility, drawdowns, extremes, benchmark)
       are computed strictly across the resolved horizon window.
  4. Benchmark Inner Alignment:
     - Rebased against S&P 500 (^GSPC) on common base date.
  5. Caching:
     - 300s TTL cache to protect providers against repetitive querying.
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from aurelius.domain.analytics.benchmark import align_and_compare_benchmark
from aurelius.domain.analytics.drawdowns import (
    calculate_drawdown_series,
    compute_drawdown_metrics,
)
from aurelius.domain.analytics.indicators import (
    calculate_ema,
    calculate_sma,
    compute_historical_extremes,
)
from aurelius.domain.analytics.returns import (
    calculate_cumulative_returns,
    calculate_simple_daily_returns,
    compute_return_metrics,
)
from aurelius.domain.analytics.volatility import (
    calculate_rolling_volatility,
    compute_volatility_metrics,
)
from aurelius.domain.entities.enums import MarketInterval
from aurelius.domain.entities.historical import (
    HistoricalAnalysisSummary,
    HistoricalBarPoint,
    HistoricalTimeHorizon,
)
from aurelius.domain.entities.ohlcv import OHLCVBar
from aurelius.domain.errors import DataNotFoundError
from aurelius.providers.base import MarketDataProvider
from aurelius.providers.registry import get_market_data_provider

logger = logging.getLogger(__name__)

DEFAULT_BENCHMARK_TICKER = "^GSPC"
DEFAULT_BENCHMARK_ID = "SP500"
DEFAULT_BENCHMARK_NAME = "S&P 500 Index"
WARMUP_CALENDAR_DAYS = 365


class HistoricalAnalysisService:
    """
    Orchestrates historical market analysis across configurable time horizons,
    performing warm-up fetches, calculating analytics, and aligning benchmarks.
    """

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._provider = provider or get_market_data_provider()
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[tuple, tuple[datetime, HistoricalAnalysisSummary]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def resolve_horizon_dates(
        horizon: HistoricalTimeHorizon,
        custom_start: date | None = None,
        custom_end: date | None = None,
        as_of_date: date | None = None,
    ) -> tuple[date, date]:
        """
        Resolve start_date and end_date for a given time horizon.
        """
        end = as_of_date or date.today()

        if horizon == HistoricalTimeHorizon.ONE_MONTH:
            start = end - timedelta(days=30)
        elif horizon == HistoricalTimeHorizon.THREE_MONTHS:
            start = end - timedelta(days=90)
        elif horizon == HistoricalTimeHorizon.SIX_MONTHS:
            start = end - timedelta(days=180)
        elif horizon == HistoricalTimeHorizon.YEAR_TO_DATE:
            start = date(end.year, 1, 1)
        elif horizon == HistoricalTimeHorizon.ONE_YEAR:
            start = end - timedelta(days=365)
        elif horizon == HistoricalTimeHorizon.THREE_YEARS:
            start = end - timedelta(days=3 * 365)
        elif horizon == HistoricalTimeHorizon.FIVE_YEARS:
            start = end - timedelta(days=5 * 365)
        elif horizon == HistoricalTimeHorizon.MAX:
            start = end - timedelta(days=7305)  # ~20 years
        elif horizon == HistoricalTimeHorizon.CUSTOM:
            if not custom_start or not custom_end:
                raise ValueError(
                    "Custom horizon requires both custom_start and custom_end."
                )
            if custom_start > custom_end:
                raise ValueError(
                    f"custom_start ({custom_start}) cannot be after custom_end ({custom_end})."
                )
            start = custom_start
            end = custom_end
        else:
            start = end - timedelta(days=365)

        return start, end

    async def analyze_security(
        self,
        ticker: str,
        horizon: HistoricalTimeHorizon = HistoricalTimeHorizon.ONE_YEAR,
        custom_start: date | None = None,
        custom_end: date | None = None,
        benchmark_ticker: str = DEFAULT_BENCHMARK_TICKER,
        include_benchmark: bool = True,
        force_refresh: bool = False,
    ) -> HistoricalAnalysisSummary:
        """
        Retrieve bars, compute analytics, and assemble HistoricalAnalysisSummary.
        """
        norm_ticker = ticker.strip().upper()
        norm_bmk = (
            benchmark_ticker.strip().upper()
            if benchmark_ticker
            else DEFAULT_BENCHMARK_TICKER
        )

        start_date, end_date = self.resolve_horizon_dates(
            horizon=horizon,
            custom_start=custom_start,
            custom_end=custom_end,
        )

        cache_key = (
            norm_ticker,
            horizon.value,
            start_date.isoformat(),
            end_date.isoformat(),
            norm_bmk if include_benchmark else None,
        )

        # Check cache
        if not force_refresh:
            async with self._lock:
                if cache_key in self._cache:
                    cached_at, summary = self._cache[cache_key]
                    if (
                        datetime.now(UTC) - cached_at
                    ).total_seconds() < self._cache_ttl_seconds:
                        return summary

        # Warm-up start date to calculate accurate 200-day moving averages
        query_start = (
            start_date
            if horizon == HistoricalTimeHorizon.MAX
            else start_date - timedelta(days=WARMUP_CALENDAR_DAYS)
        )

        # Concurrently fetch security bars and benchmark bars
        tasks = [
            self._provider.get_historical_bars(
                norm_ticker,
                start=query_start,
                end=end_date,
                interval=MarketInterval.DAILY,
            )
        ]
        if include_benchmark:
            tasks.append(
                self._provider.get_historical_bars(
                    norm_bmk,
                    start=query_start,
                    end=end_date,
                    interval=MarketInterval.DAILY,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        sec_res = results[0]
        if isinstance(sec_res, Exception):
            raise sec_res

        sec_series = sec_res
        if not sec_series.bars:
            raise DataNotFoundError(
                f"No historical price bars available for '{norm_ticker}' between {start_date} and {end_date}."
            )

        bmk_bars: list[OHLCVBar] = []
        if include_benchmark and len(results) > 1:
            bmk_res = results[1]
            if isinstance(bmk_res, Exception):
                logger.warning("Benchmark fetch failed for '%s': %s", norm_bmk, bmk_res)
            else:
                bmk_bars = bmk_res.bars

        # Sort security bars chronologically
        all_sec_bars = sorted(sec_series.bars, key=lambda b: b.timestamp)

        # Compute technical indicators over ALL bars (including warm-up) on raw Close
        all_raw_closes = [b.close for b in all_sec_bars]
        all_sma_20 = calculate_sma(all_raw_closes, window=20)
        all_sma_50 = calculate_sma(all_raw_closes, window=50)
        all_sma_200 = calculate_sma(all_raw_closes, window=200)
        all_ema_20 = calculate_ema(all_raw_closes, window=20)

        # Compute rolling volatility over all bars on adj_close
        all_adj_closes = [
            b.adj_close if b.adj_close is not None else b.close for b in all_sec_bars
        ]
        all_rolling_vol_20 = calculate_rolling_volatility(
            all_adj_closes, window_returns=20
        )

        # Filter bars to horizon display window: bar.timestamp >= start_date
        # Keep track of indices into all_sec_bars
        display_indices = [
            i
            for i, b in enumerate(all_sec_bars)
            if (b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp)
            >= start_date
        ]

        if not display_indices:
            # Fallback if start_date is slightly beyond latest bar: take whatever bars exist
            display_indices = list(range(len(all_sec_bars)))

        display_bars = [all_sec_bars[i] for i in display_indices]
        display_raw_closes = [all_raw_closes[i] for i in display_indices]
        display_adj_closes = [all_adj_closes[i] for i in display_indices]
        display_dates = [
            (b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp)
            for b in display_bars
        ]

        # Calculate returns, cumulative returns, and drawdowns strictly across display window
        display_daily_returns = calculate_simple_daily_returns(display_adj_closes)
        display_cumulative_returns = calculate_cumulative_returns(display_adj_closes)
        display_drawdowns = calculate_drawdown_series(display_adj_closes)

        # Benchmark comparison over display window
        bmk_comparison = None
        bmk_cumulative_map: dict[date, Decimal] = {}
        if include_benchmark and bmk_bars:
            bmk_comparison, bmk_cumulative_map = align_and_compare_benchmark(
                security_bars=display_bars,
                benchmark_bars=bmk_bars,
                benchmark_id=DEFAULT_BENCHMARK_ID,
                benchmark_name=DEFAULT_BENCHMARK_NAME,
            )

        # Construct HistoricalBarPoints
        bar_points: list[HistoricalBarPoint] = []
        for local_idx, global_idx in enumerate(display_indices):
            bar = all_sec_bars[global_idx]
            bar_date = display_dates[local_idx]
            adj_p = display_adj_closes[local_idx]

            point = HistoricalBarPoint(
                date=bar_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                adj_close=adj_p,
                volume=bar.volume,
                daily_return=display_daily_returns[local_idx],
                cumulative_return=display_cumulative_returns[local_idx],
                drawdown=display_drawdowns[local_idx],
                sma_20=all_sma_20[global_idx],
                sma_50=all_sma_50[global_idx],
                sma_200=all_sma_200[global_idx],
                ema_20=all_ema_20[global_idx],
                rolling_vol_20=all_rolling_vol_20[global_idx],
                benchmark_cumulative_return=bmk_cumulative_map.get(bar_date),
            )
            bar_points.append(point)

        # Compute summary metrics over display window
        return_metrics = compute_return_metrics(display_adj_closes, display_dates)
        vol_metrics = compute_volatility_metrics(display_adj_closes)
        dd_metrics = compute_drawdown_metrics(display_adj_closes, display_dates)
        extremes = compute_historical_extremes(display_raw_closes, display_dates)

        actual_start_date = display_dates[0]
        actual_end_date = display_dates[-1]
        calendar_days = (actual_end_date - actual_start_date).days
        trading_days = len(display_dates)

        summary = HistoricalAnalysisSummary(
            ticker=norm_ticker,
            horizon=horizon,
            start_date=actual_start_date,
            end_date=actual_end_date,
            calendar_days=calendar_days,
            trading_days=trading_days,
            returns=return_metrics,
            volatility=vol_metrics,
            drawdowns=dd_metrics,
            extremes=extremes,
            benchmark_comparison=bmk_comparison,
            series=bar_points,
            provider=self._provider.name,
            fetched_at=datetime.now(UTC),
        )

        async with self._lock:
            self._cache[cache_key] = (datetime.now(UTC), summary)

        return summary


_historical_service_instance: HistoricalAnalysisService | None = None


def get_historical_analysis_service() -> HistoricalAnalysisService:
    """Dependency provider for HistoricalAnalysisService singleton."""
    global _historical_service_instance
    if _historical_service_instance is None:
        _historical_service_instance = HistoricalAnalysisService()
    return _historical_service_instance
