from unittest.mock import Mock

import pandas as pd
from pydantic import SecretStr

from app.agents.research_agent.graph import ResearchAgent
from app.agents.research_agent.nodes import build_research_report
from app.agents.shared.llm import ResearchNarrator
from app.analysis.indicators import calculate_indicators
from app.strategies.base import TradeSignal
from app.strategies.strategy_engine import StrategyEngine


def make_bars(count=90):
    dates = pd.date_range("2025-01-01", periods=count, freq="D", tz="UTC")
    closes = [100 + index for index in range(count)]
    return [
        {
            "timestamp": timestamp.isoformat(),
            "open": close - 0.25,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 100_000,
        }
        for timestamp, close in zip(dates, closes)
    ]


def test_indicator_calculation_uses_required_windows():
    bars = make_bars(60)
    history = pd.DataFrame(bars).set_index("timestamp")
    indicators = calculate_indicators(history)
    assert indicators["sma_50"] == 134.5
    assert indicators["rsi_14"] == 100.0
    assert indicators["atr_14"] > 0
    assert indicators["historical_volatility_20"] is not None


def test_insufficient_history_does_not_create_indicator_values():
    history = pd.DataFrame(make_bars(5)).set_index("timestamp")
    indicators = calculate_indicators(history)
    assert indicators["sma_50"] is None
    decision = StrategyEngine().evaluate(105, indicators)
    assert decision.signal == TradeSignal.INSUFFICIENT_DATA


def test_research_report_contains_consensus_and_bounded_trade_levels():
    report = build_research_report("MSFT", make_bars(), [])
    assert report.signal == TradeSignal.BUY
    assert report.proposed_stop_loss < report.latest_price
    assert report.proposed_take_profit > report.latest_price
    assert report.decision.buy_votes >= 2
    assert report.limitations


def test_research_agent_fetches_and_adds_deterministic_explanation():
    market_data = Mock()
    market_data.fetch_and_store.return_value = {"data": make_bars(), "issues": []}
    agent = ResearchAgent(market_data, ResearchNarrator(None, "unused"))
    report = agent.run("msft", period="6mo", interval="1d")
    assert report.ticker == "MSFT"
    assert report.interpretation_source == "deterministic"
    assert "BUY" in report.interpretation
    market_data.fetch_and_store.assert_called_once_with("msft", period="6mo", interval="1d")


def test_openai_narrator_uses_response_text_without_changing_signal(monkeypatch):
    report = build_research_report("MSFT", make_bars(), [])
    response = Mock()
    response.json.return_value = {
        "output": [{
            "type": "message",
            "content": [{"type": "output_text", "text": "Several indicators align, with uncertainty."}],
        }]
    }
    post = Mock(return_value=response)
    monkeypatch.setattr("app.agents.shared.llm.httpx.post", post)
    narrator = ResearchNarrator(SecretStr("test-key"), "test-model")
    interpretation, source = narrator.interpret(report)
    assert interpretation.startswith("Several indicators")
    assert source == "openai"
    assert report.signal == report.decision.signal
    assert post.call_args.kwargs["json"]["model"] == "test-model"
