"""Abstract market data provider interface.

All providers -- Yahoo Finance, a mock provider used in tests, a future
Polygon / Alpha Vantage integration -- implement this single contract, so the
rest of the system can depend on the interface instead of on any concrete
class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

# (ticker, [raw timestamp, open, high, low, close, volume])
TickerData = dict[str, pd.DataFrame]


class MarketDataProvider(ABC):
    """Contract every market-data provider must fulfill.

    Responsibilities
    ----------------
    * Convert raw external data into the project's internal ``TickerData``
      format before handing it back (the service layer never sees raw API
      payloads).
    * Raise typed exceptions (``ProviderError`` subclasses) instead of generic
      ``Exception`` so callers can branch on failure type.
    * Never persist anything: the provider only *reads*.
    """

    @abstractmethod
    def fetch_history(
        self, ticker: str | None = None, **fetch_kwargs: Any
    ) -> TickerData:
        """Return historical OHLCV for the configured ticker(s).

        ``**fetch_kwargs`` keeps the interface stable for future providers
        that fetch by explicit date range instead of period/interval.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_history_period_interval(
        self,
        ticker: str | None = None,
        *,
        period: str = "1mo",
        interval: str = "1d",
    ) -> TickerData:
        """Fetch the selected ticker using a period and interval."""
        raise NotImplementedError


class ProviderError(Exception):
    """Base error for anything raised by a market data provider."""


class ProviderInvalidTicker(ProviderError):
    """The requested ticker is invalid / could not be resolved."""


class ProviderNetworkError(ProviderError):
    """A network or HTTP error occurred while contacting the provider."""


class ProviderEmptyResponse(ProviderError):
    """The provider returned data, but not a single OHLCV row."""

    def __init__(self, message: str, payload: Any = None) -> None:
        super().__init__(message)
        self.payload = payload


class ProviderRateLimitError(ProviderError):
    """The provider throttled us (429 / rate limit)."""
