"""Yahoo Finance market data provider, isolated from the API and database."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

from app.market_data.providers.interfaces import (
    MarketDataProvider,
    ProviderEmptyResponse,
    ProviderError,
    ProviderInvalidTicker,
    ProviderNetworkError,
    ProviderRateLimitError,
)

logger = logging.getLogger(__name__)

SUPPORTED_INTERVALS = frozenset(
    {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"}
)
SUPPORTED_PERIODS = frozenset(
    {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
)
OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


class YahooFinanceProvider(MarketDataProvider):
    """Fetch OHLCV history, the latest bar, and profile details from Yahoo."""

    def __init__(self, ticker: str | None = None) -> None:
        self.ticker = ticker.upper().strip() if ticker else None

    def fetch_history(
        self,
        ticker: str | None = None,
        *,
        period: str = "1mo",
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, pd.DataFrame]:
        symbol = self._symbol(ticker)
        self._validate_interval(interval)
        if (start is None) != (end is None):
            raise ValueError("start and end must be supplied together")
        if start is None and period not in SUPPORTED_PERIODS:
            raise ValueError(f"Unsupported history period: {period}")
        try:
            instrument = yf.Ticker(symbol)
            options: dict[str, Any] = {"interval": interval, "auto_adjust": False, "actions": False}
            if start is None:
                options["period"] = period
            else:
                options.update(start=start, end=end)
            frame = instrument.history(**options)
        except Exception as exc:
            logger.warning("Yahoo history request failed for %s: %s", symbol, exc)
            if "429" in str(exc) or "rate limit" in str(exc).lower():
                raise ProviderRateLimitError(f"Yahoo Finance rate limited {symbol}") from exc
            raise ProviderNetworkError(f"Yahoo Finance could not retrieve {symbol}") from exc
        if frame is None or frame.empty:
            try:
                info = instrument.get_info()
            except Exception as exc:
                if "429" in str(exc) or "rate limit" in str(exc).lower():
                    raise ProviderRateLimitError(f"Yahoo Finance rate limited {symbol}") from exc
                raise ProviderNetworkError(
                    f"Yahoo Finance could not confirm whether {symbol} is valid"
                ) from exc
            if info and any(info.get(key) for key in ("shortName", "longName", "symbol")):
                raise ProviderEmptyResponse(f"Yahoo Finance has no history for '{symbol}'")
            raise ProviderInvalidTicker(f"Yahoo Finance returned no history for '{symbol}'")
        frame = self._normalize_columns(frame)
        missing = [column for column in OHLCV_COLUMNS if column not in frame.columns]
        if missing:
            raise ProviderEmptyResponse(
                f"Yahoo Finance response for {symbol} is missing columns: {', '.join(missing)}",
                payload=frame,
            )
        return {symbol: frame.loc[:, list(OHLCV_COLUMNS)].copy()}

    def fetch_history_period_interval(
        self, ticker: str | None = None, *, period: str = "1mo", interval: str = "1d"
    ) -> dict[str, pd.DataFrame]:
        return self.fetch_history(ticker, period=period, interval=interval)

    def fetch_latest(self, ticker: str | None = None) -> dict[str, Any]:
        """Return the newest available OHLCV bar for the ticker."""
        symbol = self._symbol(ticker)
        for period, interval in (("5d", "1m"), ("5d", "1d")):
            try:
                history = self.fetch_history(symbol, period=period, interval=interval)[symbol]
            except ProviderInvalidTicker:
                if interval == "1d":
                    raise
                continue
            except ProviderError:
                if interval == "1d":
                    raise
                continue
            if not history.empty:
                timestamp = pd.Timestamp(history.index[-1])
                if timestamp.tzinfo is None:
                    timestamp = timestamp.tz_localize("UTC")
                else:
                    timestamp = timestamp.tz_convert("UTC")
                row = history.iloc[-1]
                return {
                    "ticker": symbol,
                    "timestamp": timestamp.isoformat(),
                    **{column: float(row[column]) for column in OHLCV_COLUMNS[:4]},
                    "volume": int(row["volume"]),
                }
        raise ProviderEmptyResponse(f"Yahoo Finance has no recent market data for '{symbol}'")

    def fetch_company_info(self, ticker: str | None = None) -> dict[str, Any]:
        """Return available company profile fields without failing history calls."""
        symbol = self._symbol(ticker)
        try:
            info = yf.Ticker(symbol).get_info()
        except Exception as exc:
            logger.info("Yahoo profile unavailable for %s: %s", symbol, exc)
            if "429" in str(exc) or "rate limit" in str(exc).lower():
                raise ProviderRateLimitError(f"Yahoo Finance rate limited {symbol}") from exc
            raise ProviderNetworkError(f"Yahoo Finance could not retrieve profile for {symbol}") from exc
        if not info or not any(info.get(key) for key in ("shortName", "longName", "symbol")):
            raise ProviderInvalidTicker(f"Yahoo Finance returned no company profile for '{symbol}'")
        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName"),
            "exchange": info.get("exchange") or info.get("fullExchangeName"),
            "sector": info.get("sector"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency"),
            "country": info.get("country"),
            "website": info.get("website"),
            "summary": info.get("longBusinessSummary"),
        }

    @staticmethod
    def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame = frame.rename(columns={column: str(column).lower() for column in frame.columns})
        return frame

    def _symbol(self, ticker: str | None) -> str:
        symbol = (ticker or self.ticker or "").strip().upper()
        if not symbol or len(symbol) > 12 or any(char.isspace() for char in symbol):
            raise ProviderInvalidTicker("A valid ticker symbol is required")
        return symbol

    @staticmethod
    def _validate_interval(interval: str) -> None:
        if interval not in SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported data interval: {interval}")
