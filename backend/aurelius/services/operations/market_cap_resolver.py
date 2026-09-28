"""
aurelius.services.operations.market_cap_resolver
================================================
Centralized resolver enforcing strict temporal compatibility rules
for market capitalization across fundamental operations.

Temporal Compatibility Invariants:
  1. The market-cap observation date (as_of_date) is compared against the financial
     period cutoff date (period.instant_date for Balance Sheet, period.end_date for duration/TTM).
  2. Temporal compatibility strictly requires exact date coincidence:
         observation.as_of_date == financial_cutoff_date
     Fuzzy date tolerances (e.g. ±N days) are forbidden.
  3. Historical financial periods (target_period != sorted_periods[-1]) require an
     historical point-in-time observation matching the cutoff date. Current market cap
     is strictly prohibited from backward substitution into historical financial periods.
  4. Missing date metadata (as_of_date is None) does NOT become VALID merely because the
     period is the latest reported period. Missing as-of date metadata returns UNAVAILABLE.
  5. Incompatible, stale, or missing observations emit DiagnosticCode.MARKET_CAP_UNAVAILABLE.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aurelius.domain.entities.financials import FinancialPeriod
from aurelius.domain.entities.market_cap import MarketCapObservation
from aurelius.domain.fundamental.enums import DiagnosticCode
from aurelius.domain.fundamental.models import MetricDiagnostic


class MarketCapResolutionStatus(StrEnum):
    VALID = "VALID"
    UNAVAILABLE_HISTORICAL_PERIOD = "UNAVAILABLE_HISTORICAL_PERIOD"
    UNAVAILABLE_MISSING_AS_OF_DATE = "UNAVAILABLE_MISSING_AS_OF_DATE"
    UNAVAILABLE_TEMPORALLY_INCOMPATIBLE = "UNAVAILABLE_TEMPORALLY_INCOMPATIBLE"
    UNAVAILABLE_NO_OBSERVATION = "UNAVAILABLE_NO_OBSERVATION"


class MarketCapResolutionResult(BaseModel):
    """
    Result of market-cap temporal compatibility resolution.
    """

    model_config = ConfigDict(frozen=True)

    status: MarketCapResolutionStatus
    value: Decimal | None = None
    observation: MarketCapObservation | None = None
    diagnostics: list[MetricDiagnostic] = Field(default_factory=list)
    methodology_notes: str = ""


class MarketCapResolver:
    """
    Centralized resolver enforcing strict temporal compatibility rules
    for market capitalization across fundamental operations.
    """

    @classmethod
    async def resolve(
        cls,
        provider: Any,
        ticker: str,
        target_period: FinancialPeriod,
        sorted_periods: list[FinancialPeriod],
    ) -> MarketCapResolutionResult:
        fin_date = target_period.end_date or target_period.instant_date
        if fin_date is None:
            return MarketCapResolutionResult(
                status=MarketCapResolutionStatus.UNAVAILABLE_TEMPORALLY_INCOMPATIBLE,
                value=None,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                        message=f"Financial period {target_period.period_key} lacks an end_date or instant_date cutoff.",
                        details={
                            "period": target_period.period_key,
                            "reason": "MISSING_FINANCIAL_CUTOFF_DATE",
                        },
                    )
                ],
                methodology_notes="Financial period cutoff date is unavailable.",
            )

        is_latest = bool(
            sorted_periods and target_period.period_key == sorted_periods[-1].period_key
        )

        obs = await cls._extract_observation(provider, ticker, target_period)
        if obs is None or obs.value is None:
            return MarketCapResolutionResult(
                status=MarketCapResolutionStatus.UNAVAILABLE_NO_OBSERVATION,
                value=None,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                        message=f"Market capitalization is unavailable from data provider for {ticker}.",
                        details={
                            "period": target_period.period_key,
                            "reason": "NO_OBSERVATION_RETURNED",
                        },
                    )
                ],
                methodology_notes="No market capitalization observation was returned by the provider.",
            )

        # Protection Rule 1: Historical periods require exact point-in-time historical observation
        # Current / non-matching market cap is strictly prohibited from backward substitution
        if not is_latest and obs.as_of_date != fin_date:
            return MarketCapResolutionResult(
                status=MarketCapResolutionStatus.UNAVAILABLE_HISTORICAL_PERIOD,
                value=None,
                observation=obs,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                        message=(
                            f"Historical financial period {target_period.period_key} requires period-compatible "
                            "historical market capitalization. Current market capitalization is strictly prohibited "
                            "from backward substitution."
                        ),
                        details={
                            "period": target_period.period_key,
                            "financial_date": fin_date.isoformat(),
                            "reason": "HISTORICAL_PERIOD_CURRENT_MARKET_CAP_PROHIBITED",
                        },
                    )
                ],
                methodology_notes=(
                    f"Period {target_period.period_key} is historical. Current market cap is prohibited "
                    "from backward substitution without verified period-end point-in-time observation."
                ),
            )

        # Protection Rule 2: Missing as-of date metadata cannot be assumed valid
        if obs.as_of_date is None:
            return MarketCapResolutionResult(
                status=MarketCapResolutionStatus.UNAVAILABLE_MISSING_AS_OF_DATE,
                value=None,
                observation=obs,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                        message=(
                            "Market capitalization observation lacks verified as-of date metadata; "
                            "temporal compatibility with financial period cannot be established."
                        ),
                        details={
                            "period": target_period.period_key,
                            "financial_date": fin_date.isoformat(),
                            "reason": "MISSING_AS_OF_DATE",
                        },
                    )
                ],
                methodology_notes="Observation lacks as_of_date metadata; temporal compatibility cannot be established.",
            )

        # Protection Rule 3: Date mismatch (stale / incompatible observation)
        if obs.as_of_date != fin_date:
            return MarketCapResolutionResult(
                status=MarketCapResolutionStatus.UNAVAILABLE_TEMPORALLY_INCOMPATIBLE,
                value=None,
                observation=obs,
                diagnostics=[
                    MetricDiagnostic(
                        code=DiagnosticCode.MARKET_CAP_UNAVAILABLE,
                        message=(
                            f"Market capitalization as-of date ({obs.as_of_date}) does not match "
                            f"financial period cutoff date ({fin_date}); temporal compatibility failed."
                        ),
                        details={
                            "period": target_period.period_key,
                            "as_of_date": obs.as_of_date.isoformat(),
                            "financial_date": fin_date.isoformat(),
                            "reason": "TEMPORAL_DATE_MISMATCH",
                        },
                    )
                ],
                methodology_notes=(
                    f"Market capitalization as-of date {obs.as_of_date} differs from "
                    f"financial period cutoff date {fin_date}."
                ),
            )

        # Rule 4: Verified temporal compatibility
        return MarketCapResolutionResult(
            status=MarketCapResolutionStatus.VALID,
            value=obs.value,
            observation=obs,
            diagnostics=[],
            methodology_notes=f"Market capitalization of {obs.value} verified temporally compatible on {fin_date}.",
        )

    @classmethod
    async def _extract_observation(
        cls,
        provider: Any,
        ticker: str,
        target_period: FinancialPeriod,
    ) -> MarketCapObservation | None:
        """
        Extract observation from provider via available provider interfaces or adapters.
        """
        if hasattr(provider, "get_market_cap_observation"):
            try:
                res = provider.get_market_cap_observation(ticker, target_period)
                if hasattr(res, "__await__"):
                    res = await res
                if isinstance(res, MarketCapObservation):
                    return res
            except Exception:
                pass

        # 2. Check for explicit observation registry on mock/test provider
        if hasattr(provider, "market_cap_observations") and isinstance(
            provider.market_cap_observations, dict
        ):
            target_key = target_period.period_key
            if target_key in provider.market_cap_observations:
                val = provider.market_cap_observations[target_key]
                if isinstance(val, MarketCapObservation):
                    return val

        # 3. Yfinance / provider _get_ticker fast_info inspection
        if hasattr(provider, "_get_ticker"):
            try:
                import asyncio

                t_obj = await asyncio.to_thread(provider._get_ticker, ticker)
                fast_info = getattr(t_obj, "fast_info", {})
                mc_raw = (
                    fast_info.get("market_cap")
                    if isinstance(fast_info, dict)
                    else getattr(fast_info, "market_cap", None)
                )
                if mc_raw is not None:
                    # Look for explicit as_of_date if attached
                    as_of_val = (
                        fast_info.get("as_of_date") or fast_info.get("asof_date")
                        if isinstance(fast_info, dict)
                        else getattr(fast_info, "as_of_date", None)
                    )
                    as_of_date: date | None = None
                    if isinstance(as_of_val, date) and not isinstance(
                        as_of_val, datetime
                    ):
                        as_of_date = as_of_val
                    elif isinstance(as_of_val, datetime):
                        as_of_date = as_of_val.date()
                    elif isinstance(as_of_val, str):
                        try:
                            as_of_date = date.fromisoformat(as_of_val)
                        except Exception:
                            as_of_date = None

                    return MarketCapObservation(
                        value=Decimal(str(mc_raw)),
                        as_of_date=as_of_date,
                        source="provider_fast_info",
                    )
            except Exception:
                return None

        return None
