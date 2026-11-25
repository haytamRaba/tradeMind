"""Market data workflow from provider through validation to persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.database.models import HistoricalPrice
from app.database.repositories import HistoricalPriceRepository, StockRepository
from app.market_data.providers.interfaces import (
    MarketDataProvider,
    ProviderEmptyResponse,
    ProviderError,
    ProviderInvalidTicker,
)
from app.market_data.validation import OHLCV_COLUMNS, ValidationResult, validate_and_normalize


class MarketDataServiceError(Exception):
    """Base error for market-data service operations."""


class MarketDataServiceStockNotFound(MarketDataServiceError):
    """No stored market data exists for the requested ticker."""


class MarketDataServiceValidationError(MarketDataServiceError):
    """The provider returned data that could not be safely persisted."""

    def __init__(self, message: str, issues: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or []


class MarketDataService:
    """Coordinate history retrieval, validation, storage, and queries."""

    def __init__(
        self,
        *,
        provider: MarketDataProvider,
        session: Session,
    ) -> None:
        self.provider = provider
        self.session = session
        self.stock_repo = StockRepository(session)
        self.price_repo = HistoricalPriceRepository(session)

    def fetch_and_store(
        self,
        ticker: str,
        *,
        period: str = "1mo",
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        symbol = self._normalize_ticker(ticker)
        start_at = self._parse_date(start)
        end_at = self._parse_date(end)
        if start_at is not None and end_at is not None and start_at > end_at:
            raise ValueError("start must be earlier than or equal to end")
        try:
            frames = self.provider.fetch_history(
                symbol, period=period, interval=interval, start=start, end=end
            )
        except (ProviderInvalidTicker, ProviderEmptyResponse):
            raise
        except ProviderError:
            raise
        except Exception as exc:
            raise MarketDataServiceError(f"Could not retrieve market data for {symbol}") from exc

        frame = frames.get(symbol)
        if frame is None and frames:
            frame = next(iter(frames.values()))
        if frame is None or frame.empty:
            raise ProviderEmptyResponse(f"Yahoo Finance returned no history for '{symbol}'")

        normalized, result = validate_and_normalize(frame, ticker=symbol)
        if result.has_errors and normalized.empty:
            raise MarketDataServiceValidationError(
                f"No valid market data rows were returned for {symbol}",
                [issue.to_dict() for issue in result.issues],
            )
        self._persist_frame(symbol, normalized)

        return {
            "ticker": symbol,
            "period": period if start is None else None,
            "interval": interval,
            "rows_fetched": len(frame),
            "rows_persisted": len(normalized),
            "issues": [issue.to_dict() for issue in result.issues],
            "data": self._serialize_frame(normalized),
        }

    def get_latest(self, ticker: str, limit: int = 1) -> list[dict[str, Any]]:
        rows = self.price_repo.get_latest(self._normalize_ticker(ticker), limit=limit)
        if not rows:
            raise MarketDataServiceStockNotFound(f"No stored history for '{ticker.upper()}'")
        return self._serialize_rows(rows)

    def get_history(
        self, ticker: str, *, start: str | None = None, end: str | None = None
    ) -> list[dict[str, Any]]:
        rows = self.price_repo.get_for_symbol(
            self._normalize_ticker(ticker),
            start=self._parse_date(start),
            end=self._parse_date(end),
        )
        if not rows:
            raise MarketDataServiceStockNotFound(f"No stored history for '{ticker.upper()}'")
        return self._serialize_rows(rows)

    def fetch_latest_and_store(self, ticker: str) -> dict[str, Any]:
        symbol = self._normalize_ticker(ticker)
        fetch_latest = getattr(self.provider, "fetch_latest", None)
        if fetch_latest is None:
            return self.fetch_and_store(symbol, period="5d", interval="1d")
        latest = fetch_latest(symbol)
        timestamp = pd.Timestamp(latest["timestamp"])
        frame = pd.DataFrame(
            [{column: latest[column] for column in OHLCV_COLUMNS}],
            index=pd.DatetimeIndex([timestamp]),
        )
        normalized, result = validate_and_normalize(frame, ticker=symbol)
        if result.has_errors or normalized.empty:
            raise MarketDataServiceValidationError(
                f"Latest market data for {symbol} failed validation",
                [issue.to_dict() for issue in result.issues],
            )
        self._persist_frame(symbol, normalized)
        return {
            "ticker": symbol,
            "period": None,
            "interval": "latest",
            "rows_fetched": 1,
            "rows_persisted": 1,
            "issues": [issue.to_dict() for issue in result.issues],
            "data": self._serialize_frame(normalized),
        }

    def _persist_frame(self, symbol: str, normalized: pd.DataFrame) -> None:
        if normalized.empty:
            return
        stock = self.stock_repo.get_by_symbol(symbol)
        if stock is None:
            company = self._company_info(symbol)
            stock = self.stock_repo.create_or_get(
                symbol=symbol,
                name=company.get("name") or symbol,
                exchange=company.get("exchange") or "UNKNOWN",
                sector=company.get("sector") or "UNKNOWN",
                market_cap=company.get("market_cap"),
                currency=company.get("currency") or "USD",
                country=company.get("country") or "UNKNOWN",
            )
        self.price_repo.create_or_update_all(self._to_model_rows(stock.id, normalized))

    def _company_info(self, ticker: str) -> dict[str, Any]:
        fetch_info = getattr(self.provider, "fetch_company_info", None)
        if fetch_info is None:
            return {}
        try:
            return fetch_info(ticker)
        except Exception:
            return {}

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        symbol = ticker.strip().upper()
        if not symbol or len(symbol) > 12:
            raise ProviderInvalidTicker("A valid ticker symbol is required")
        return symbol

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid ISO-8601 date: {value}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _to_model_rows(stock_id: int, frame: pd.DataFrame) -> list[HistoricalPrice]:
        return [
            HistoricalPrice(
                stock_id=stock_id,
                timestamp=timestamp.to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
                source="yahoo_finance",
            )
            for timestamp, row in frame.loc[:, OHLCV_COLUMNS].iterrows()
        ]

    @staticmethod
    def _serialize_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            {"timestamp": timestamp.isoformat(), **row.astype(float).to_dict(), "volume": int(row["volume"])}
            for timestamp, row in frame.iterrows()
        ]

    @staticmethod
    def _serialize_rows(rows: list[HistoricalPrice]) -> list[dict[str, Any]]:
        return [
            {
                "timestamp": row.timestamp.isoformat(),
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
                "source": row.source,
            }
            for row in rows
        ]
