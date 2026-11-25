"""Trend-following strategy using price, long average, and RSI alignment."""

from app.strategies.base import Strategy, StrategyResult, TradeSignal


class TrendFollowing(Strategy):
    name = "trend_following"

    def evaluate(self, latest_price: float, indicators: dict[str, float | None]) -> StrategyResult:
        baseline = indicators.get("sma_50")
        rsi = indicators.get("rsi_14")
        if baseline is None or rsi is None:
            return StrategyResult(strategy=self.name, signal=TradeSignal.INSUFFICIENT_DATA)
        if latest_price > baseline and rsi > 50:
            signal = TradeSignal.BUY
        elif latest_price < baseline and rsi < 50:
            signal = TradeSignal.SELL
        else:
            signal = TradeSignal.HOLD
        return StrategyResult(
            strategy=self.name,
            signal=signal,
            evidence=[f"Close={latest_price:.4f}", f"SMA(50)={baseline:.4f}", f"RSI(14)={rsi:.2f}"],
        )
