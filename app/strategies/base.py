"""Shared signal and strategy result types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, Field


class TradeSignal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class StrategyResult(BaseModel):
    strategy: str
    signal: TradeSignal
    evidence: list[str] = Field(default_factory=list)


class Strategy(ABC):
    name: str

    @abstractmethod
    def evaluate(
        self, latest_price: float, indicators: dict[str, float | None]
    ) -> StrategyResult:
        """Return a signal and the evidence behind it."""
