"""Structured research agent output."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.strategies.base import TradeSignal
from app.strategies.strategy_engine import StrategyDecision


class ResearchReport(BaseModel):
    ticker: str
    generated_at: datetime
    latest_price: float
    observations: int = Field(ge=0)
    indicators: dict[str, float | None]
    decision: StrategyDecision
    signal: TradeSignal
    proposed_stop_loss: float | None = None
    proposed_take_profit: float | None = None
    interpretation: str
    interpretation_source: Literal["deterministic", "openai"]
    data_issues: list[dict]
    limitations: list[str]
