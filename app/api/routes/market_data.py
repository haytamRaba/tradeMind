"""HTTP endpoints for historical and latest stock market data."""

from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_market_data_service
from app.api.schemas.market_data import (
    HealthResponse,
    MarketBar,
    MarketDataResponse,
    MarketHistoryResponse,
)
from app.market_data.providers.interfaces import (
    ProviderEmptyResponse,
    ProviderError,
    ProviderInvalidTicker,
    ProviderNetworkError,
    ProviderRateLimitError,
)
from app.market_data.service import (
    MarketDataService,
    MarketDataServiceError,
    MarketDataServiceStockNotFound,
    MarketDataServiceValidationError,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/market-data/{ticker}", response_model=MarketDataResponse, tags=["market data"])
def get_market_data(
    ticker: str,
    period: Annotated[str, Query(description="Yahoo Finance history period")] = "1mo",
    interval: Annotated[str, Query(description="Yahoo Finance bar interval")] = "1d",
    service: MarketDataService = Depends(get_market_data_service),
) -> dict:
    try:
        return service.fetch_and_store(ticker, period=period, interval=interval)
    except Exception as exc:
        _raise_market_data_error(exc)


@router.get("/market-data/{ticker}/latest", response_model=MarketBar, tags=["market data"])
def get_latest_market_data(
    ticker: str,
    service: MarketDataService = Depends(get_market_data_service),
) -> dict:
    try:
        result = service.fetch_latest_and_store(ticker)
        return {**result["data"][-1], "source": "yahoo_finance"}
    except Exception as exc:
        _raise_market_data_error(exc)


@router.get("/market-data/{ticker}/history", response_model=MarketHistoryResponse, tags=["market data"])
def get_market_history(
    ticker: str,
    start: Annotated[datetime | None, Query(description="Inclusive ISO-8601 timestamp")] = None,
    end: Annotated[datetime | None, Query(description="Inclusive ISO-8601 timestamp")] = None,
    service: MarketDataService = Depends(get_market_data_service),
) -> dict:
    if (start is None) != (end is None):
        raise HTTPException(status_code=422, detail="start and end must be provided together")
    try:
        if start is not None and end is not None:
            service.fetch_and_store(ticker, start=start.isoformat(), end=end.isoformat())
        bars = service.get_history(
            ticker,
            start=start.isoformat() if start else None,
            end=end.isoformat() if end else None,
        )
        return {"ticker": ticker.upper(), "count": len(bars), "data": bars}
    except Exception as exc:
        _raise_market_data_error(exc)


def _raise_market_data_error(exc: Exception) -> None:
    if isinstance(exc, ProviderRateLimitError):
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    if isinstance(exc, ProviderInvalidTicker):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (ProviderEmptyResponse, MarketDataServiceStockNotFound)):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ProviderNetworkError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, MarketDataServiceValidationError):
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "issues": exc.issues},
        ) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, (ProviderError, MarketDataServiceError)):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail="Unexpected market data error") from exc
