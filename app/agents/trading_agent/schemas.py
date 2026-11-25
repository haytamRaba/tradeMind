"""Paper-trading response types."""

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class TradeExecutionRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=64)


class PaperOrderResponse(BaseModel):
    order_id: int | None = None
    ticker: str
    side: str
    status: Literal["FILLED", "REJECTED", "SKIPPED"]
    quantity: Decimal
    execution_price: Decimal
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    realized_pnl: Decimal
    cash_after: Decimal | None = None
    idempotency_key: str
    message: str
    replayed: bool = False


class PositionSummary(BaseModel):
    ticker: str
    quantity: Decimal
    average_entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None = None
    latest_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal


class PaperPortfolioResponse(BaseModel):
    name: str
    starting_cash: Decimal
    cash: Decimal
    equity: Decimal
    market_exposure: Decimal
    unrealized_pnl: Decimal
    realized_pnl_today: Decimal
    positions: list[PositionSummary]


class ProtectiveMonitorResponse(BaseModel):
    refreshed: list[str]
    errors: list[dict[str, Any]]
    exits: list[PaperOrderResponse]
