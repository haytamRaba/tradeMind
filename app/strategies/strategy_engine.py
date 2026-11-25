"""Evaluate independent strategies and combine their signals by consensus."""

from pydantic import BaseModel

from app.strategies.base import Strategy, StrategyResult, TradeSignal
from app.strategies.macd_momentum import MACDMomentum
from app.strategies.moving_average import MovingAverageCrossover
from app.strategies.rsi_mean_reversion import RSIMeanReversion
from app.strategies.trend_following import TrendFollowing


class StrategyDecision(BaseModel):
    signal: TradeSignal
    strategies: list[StrategyResult]
    buy_votes: int
    sell_votes: int
    hold_votes: int


class StrategyEngine:
    """Run the configured strategy set without placing orders."""

    def __init__(self, strategies: list[Strategy] | None = None) -> None:
        self.strategies = strategies or [
            MovingAverageCrossover(),
            RSIMeanReversion(),
            MACDMomentum(),
            TrendFollowing(),
        ]

    def evaluate(
        self, latest_price: float, indicators: dict[str, float | None]
    ) -> StrategyDecision:
        results = [strategy.evaluate(latest_price, indicators) for strategy in self.strategies]
        votes = [result.signal for result in results if result.signal != TradeSignal.INSUFFICIENT_DATA]
        buys = votes.count(TradeSignal.BUY)
        sells = votes.count(TradeSignal.SELL)
        holds = votes.count(TradeSignal.HOLD)
        if len(votes) < 2:
            signal = TradeSignal.INSUFFICIENT_DATA
        elif buys >= 2 and buys > sells:
            signal = TradeSignal.BUY
        elif sells >= 2 and sells > buys:
            signal = TradeSignal.SELL
        else:
            signal = TradeSignal.HOLD
        return StrategyDecision(
            signal=signal,
            strategies=results,
            buy_votes=buys,
            sell_votes=sells,
            hold_votes=holds,
        )
