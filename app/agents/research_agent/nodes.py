"""Pure research nodes that transform validated bars into a report."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.agents.research_agent.schemas import ResearchReport
from app.analysis.indicators import calculate_indicators
from app.strategies.base import TradeSignal
from app.strategies.strategy_engine import StrategyEngine


def build_research_report(
    ticker: str,
    bars: list[dict[str, Any]],
    data_issues: list[dict[str, Any]],
    *,
    strategy_engine: StrategyEngine | None = None,
) -> ResearchReport:
    if not bars:
        raise ValueError(f"No validated market bars are available for {ticker}")
    history = pd.DataFrame(bars)
    history["timestamp"] = pd.to_datetime(history["timestamp"], utc=True, errors="raise")
    history = history.set_index("timestamp").sort_index()
    indicators = calculate_indicators(history)
    latest_price = float(history["close"].iloc[-1])
    decision = (strategy_engine or StrategyEngine()).evaluate(latest_price, indicators)

    atr = indicators.get("atr_14")
    stop_loss = None
    take_profit = None
    if decision.signal == TradeSignal.BUY and atr is not None and atr > 0:
        candidate_stop = latest_price - 2 * atr
        if 0 < candidate_stop < latest_price:
            stop_loss = candidate_stop
            take_profit = latest_price + 3 * atr

    limitations = [
        "Strategy signals are rule-based observations, not guaranteed predictions or trade instructions.",
        "This report does not include fundamental analysis or a full historical backtest.",
    ]
    if len(history) < 50:
        limitations.append("Fewer than 50 bars are available; long-term indicators may be missing.")
    if data_issues:
        limitations.append("The market-data provider reported quality issues for this fetch.")

    return ResearchReport(
        ticker=ticker.upper(),
        generated_at=datetime.now(timezone.utc),
        latest_price=latest_price,
        observations=len(history),
        indicators=indicators,
        decision=decision,
        signal=decision.signal,
        proposed_stop_loss=stop_loss,
        proposed_take_profit=take_profit,
        interpretation="",
        interpretation_source="deterministic",
        data_issues=data_issues,
        limitations=limitations,
    )
