"""MACD momentum strategy."""

from app.strategies.base import Strategy, StrategyResult, TradeSignal


class MACDMomentum(Strategy):
    name = "macd_momentum"

    def evaluate(self, latest_price: float, indicators: dict[str, float | None]) -> StrategyResult:
        macd = indicators.get("macd")
        signal_line = indicators.get("macd_signal")
        if macd is None or signal_line is None:
            return StrategyResult(strategy=self.name, signal=TradeSignal.INSUFFICIENT_DATA)
        if macd > signal_line and macd > 0:
            signal = TradeSignal.BUY
        elif macd < signal_line and macd < 0:
            signal = TradeSignal.SELL
        else:
            signal = TradeSignal.HOLD
        return StrategyResult(
            strategy=self.name,
            signal=signal,
            evidence=[f"MACD={macd:.4f}", f"Signal line={signal_line:.4f}"],
        )
