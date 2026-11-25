"""Moving-average trend crossover strategy."""

from app.strategies.base import Strategy, StrategyResult, TradeSignal


class MovingAverageCrossover(Strategy):
    name = "moving_average_crossover"

    def evaluate(self, latest_price: float, indicators: dict[str, float | None]) -> StrategyResult:
        short = indicators.get("sma_20")
        long = indicators.get("sma_50")
        if short is None or long is None:
            return StrategyResult(strategy=self.name, signal=TradeSignal.INSUFFICIENT_DATA)
        evidence = [f"SMA(20)={short:.4f}", f"SMA(50)={long:.4f}", f"Close={latest_price:.4f}"]
        if short > long and latest_price > short:
            signal = TradeSignal.BUY
        elif short < long and latest_price < short:
            signal = TradeSignal.SELL
        else:
            signal = TradeSignal.HOLD
        return StrategyResult(strategy=self.name, signal=signal, evidence=evidence)
