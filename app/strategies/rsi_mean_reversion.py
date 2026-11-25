"""RSI mean-reversion strategy with explicit threshold evidence."""

from app.strategies.base import Strategy, StrategyResult, TradeSignal


class RSIMeanReversion(Strategy):
    name = "rsi_mean_reversion"

    def evaluate(self, latest_price: float, indicators: dict[str, float | None]) -> StrategyResult:
        rsi = indicators.get("rsi_14")
        if rsi is None:
            return StrategyResult(strategy=self.name, signal=TradeSignal.INSUFFICIENT_DATA)
        if rsi <= 30:
            signal = TradeSignal.BUY
        elif rsi >= 70:
            signal = TradeSignal.SELL
        else:
            signal = TradeSignal.HOLD
        return StrategyResult(
            strategy=self.name,
            signal=signal,
            evidence=[f"RSI(14)={rsi:.2f}", "Oversold <= 30; overbought >= 70"],
        )
