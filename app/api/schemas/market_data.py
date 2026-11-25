"""Response schemas for market-data endpoints."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "TradeMind market data API"


class MarketBar(BaseModel):
    model_config = ConfigDict(extra="allow")

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str | None = None


class MarketDataResponse(BaseModel):
    ticker: str
    period: str | None = None
    interval: str
    rows_fetched: int = Field(ge=0)
    rows_persisted: int = Field(ge=0)
    issues: list[dict[str, Any]]
    data: list[MarketBar]


class MarketHistoryResponse(BaseModel):
    ticker: str
    count: int = Field(ge=0)
    data: list[MarketBar]
