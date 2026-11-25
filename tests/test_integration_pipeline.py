"""Integration tests for full agent pipeline: data → research → trade → monitor.

Tests the complete flow using SQLite in-memory database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.agents.research_agent.graph import ResearchAgent
from app.agents.research_agent.nodes import build_research_report
from app.agents.shared.llm import ResearchNarrator
from app.agents.trading_agent.graph import TradingAgent
from app.config import Settings
from app.database.models import HistoricalPrice
from app.database.repositories import HistoricalPriceRepository, StockRepository
from app.execution.paper_trading import PaperTradingService
from app.market_data.providers.yahoo import YahooFinanceProvider
from app.market_data.service import MarketDataService
from app.strategies.base import TradeSignal


def add_stock_and_bars(session, *, ticker="MSFT", count=60, start_price=100, trend="up"):
    """Add stock with multiple bars for testing."""
    stock = StockRepository(session).create_or_get(
        ticker,
        name=ticker,
        exchange="NASDAQ",
        sector="Technology",
        currency="USD",
        country="US",
    )
    import pandas as pd
    dates = pd.date_range("2025-01-01", periods=count, freq="D", tz="UTC")
    if trend == "up":
        price_func = lambda i: start_price + i
    else:
        price_func = lambda i: start_price - i
    bars = [
        HistoricalPrice(
            stock_id=stock.id,
            timestamp=ts.to_pydatetime(),
            open=price_func(i) - 0.5,
            high=price_func(i) + 1,
            low=price_func(i) - 1,
            close=price_func(i),
            volume=100_000,
            source="test",
        )
        for i, ts in enumerate(dates)
    ]
    HistoricalPriceRepository(session).create_or_update_all(bars)
    session.commit()
    return stock


def make_trader_and_agents(session):
    """Create paper trading service and agents for testing."""
    settings = Settings(paper_initial_cash=100_000)
    market_data = MarketDataService(provider=YahooFinanceProvider(), session=session)
    narrator = ResearchNarrator(None, "gpt-6.2-sol")
    research_agent = ResearchAgent(market_data=market_data, narrator=narrator)
    paper_trading = PaperTradingService(session, settings=settings)
    trading_agent = TradingAgent(paper_trading=paper_trading, market_data=market_data)
    return research_agent, trading_agent, paper_trading


def test_full_pipeline_buy_signal(db_session):
    """Test complete pipeline: seed data → research → execute → monitor."""
    add_stock_and_bars(db_session, ticker="MSFT", count=60, start_price=100)

    research_agent, trading_agent, paper_trading = make_trader_and_agents(db_session)

    price_repo = HistoricalPriceRepository(db_session)
    stock = StockRepository(db_session).get_by_symbol("MSFT")
    prices = price_repo.get_latest("MSFT", limit=60)

    bars = [
        {
            "timestamp": p.timestamp.isoformat(),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
            "volume": p.volume,
        }
        for p in prices
    ]

    report = build_research_report("MSFT", bars, [])
    interpretation, source = ResearchNarrator(None, "gpt-6.2-sol").interpret(report)
    report = report.model_copy(update={"interpretation": interpretation, "interpretation_source": source})

    assert report.signal == TradeSignal.BUY
    assert report.proposed_stop_loss is not None
    assert report.proposed_take_profit is not None
    assert report.proposed_stop_loss < report.latest_price
    assert report.proposed_take_profit > report.latest_price

    execution = trading_agent.execute(report, idempotency_key="integration-test-buy")
    assert execution["status"] == "FILLED"
    assert execution["side"] == "BUY"
    assert execution["quantity"] > 0

    portfolio = trading_agent.get_portfolio()
    assert len(portfolio["positions"]) == 1
    assert portfolio["positions"][0]["ticker"] == "MSFT"
    assert portfolio["cash"] < Decimal("100000")

    # Monitor using paper_trading directly (uses stored data, not live API)
    monitor_result = paper_trading.monitor_protective_levels()
    assert len(monitor_result) == 0  # Price 159 is between stop 155 and target 165


def test_full_pipeline_sell_signal(db_session):
    """Test pipeline with downward trend triggering SELL."""
    add_stock_and_bars(db_session, ticker="AAPL", count=60, start_price=200, trend="down")

    research_agent, trading_agent, paper_trading = make_trader_and_agents(db_session)

    price_repo = HistoricalPriceRepository(db_session)
    stock = StockRepository(db_session).get_by_symbol("AAPL")
    prices = price_repo.get_latest("AAPL", limit=60)
    prices = list(reversed(prices))  # get_latest returns DESC, need ASC for build_research_report

    bars = [
        {
            "timestamp": p.timestamp.isoformat(),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
            "volume": p.volume,
        }
        for p in prices
    ]

    report = build_research_report("AAPL", bars, [])
    interpretation, source = ResearchNarrator(None, "gpt-6.2-sol").interpret(report)
    report = report.model_copy(update={"interpretation": interpretation, "interpretation_source": source})

    assert report.signal == TradeSignal.SELL

    execution = trading_agent.execute(report, idempotency_key="integration-test-sell")
    assert execution["status"] == "REJECTED"
    assert "no open position" in execution["message"].lower()


def test_idempotent_replay(db_session):
    """Test that same idempotency key replays the order."""
    add_stock_and_bars(db_session, ticker="GOOGL", count=60, start_price=150)

    _, trading_agent, _ = make_trader_and_agents(db_session)

    price_repo = HistoricalPriceRepository(db_session)
    stock = StockRepository(db_session).get_by_symbol("GOOGL")
    prices = price_repo.get_latest("GOOGL", limit=60)

    bars = [
        {
            "timestamp": p.timestamp.isoformat(),
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
            "volume": p.volume,
        }
        for p in prices
    ]

    report = build_research_report("GOOGL", bars, [])
    interpretation, source = ResearchNarrator(None, "gpt-6.2-sol").interpret(report)
    report = report.model_copy(update={"interpretation": interpretation, "interpretation_source": source})

    exec1 = trading_agent.execute(report, idempotency_key="idem-test-1")
    assert exec1["status"] == "FILLED"
    assert exec1["replayed"] is False

    exec2 = trading_agent.execute(report, idempotency_key="idem-test-1")
    assert exec2["status"] == "FILLED"
    assert exec2["replayed"] is True
    assert exec2["order_id"] == exec1["order_id"]


def test_protective_stop_trigger(db_session):
    """Test that protective stop closes position when price crosses."""
    # First, create upward trend to generate BUY signal and open position
    add_stock_and_bars(db_session, ticker="TSLA", count=60, start_price=100, trend="up")
    db_session.commit()

    _, trading_agent, paper_trading = make_trader_and_agents(db_session)

    price_repo = HistoricalPriceRepository(db_session)
    prices = list(reversed(price_repo.get_for_symbol("TSLA")))
    bars = [
        {"timestamp": p.timestamp.isoformat(), "open": p.open, "high": p.high, "low": p.low, "close": p.close, "volume": p.volume}
        for p in prices
    ]
    report = build_research_report("TSLA", bars, [])
    interpretation, source = ResearchNarrator(None, "gpt-6.2-sol").interpret(report)
    report = report.model_copy(update={"interpretation": interpretation, "interpretation_source": source})

    # Execute BUY to open position with stop loss
    execution = trading_agent.execute(report, idempotency_key="stop-test")
    assert execution["status"] == "FILLED"

    # Now add a new price bar BELOW the stop loss to trigger the stop
    # Get the position's stop loss
    portfolio = trading_agent.get_portfolio()
    position = portfolio["positions"][0]
    stop_loss = float(position["stop_loss"])

    # Add a new bar with price below stop loss
    stock = StockRepository(db_session).get_by_symbol("TSLA")
    from app.database.models import HistoricalPrice
    from datetime import datetime, timezone
    new_price = stop_loss - 1.0  # Below stop loss
    new_bar = HistoricalPrice(
        stock_id=stock.id,
        timestamp=datetime.now(timezone.utc),
        open=new_price,
        high=new_price + 0.5,
        low=new_price - 0.5,
        close=new_price,
        volume=100_000,
        source="test",
    )
    HistoricalPriceRepository(db_session).create_or_update(new_bar)
    db_session.commit()

    # Monitor should now trigger the stop
    monitor_result = paper_trading.monitor_protective_levels()
    assert len(monitor_result) == 1
    assert monitor_result[0]["side"] == "SELL"
    assert "stop crossed" in monitor_result[0]["message"].lower()

    portfolio = trading_agent.get_portfolio()
    assert len(portfolio["positions"]) == 0


def test_daily_loss_limit_enforcement(db_session):
    """Test that daily loss limit blocks new buys."""
    # First, create upward trend to generate BUY signal
    add_stock_and_bars(db_session, ticker="NVDA", count=60, start_price=100, trend="up")
    db_session.commit()

    settings = Settings(paper_initial_cash=10_000, max_daily_loss_pct=0.05)
    market_data = MarketDataService(provider=YahooFinanceProvider(), session=db_session)
    narrator = ResearchNarrator(None, "gpt-6.2-sol")
    paper_trading = PaperTradingService(db_session, settings=settings)
    trading_agent = TradingAgent(paper_trading=paper_trading, market_data=market_data)

    price_repo = HistoricalPriceRepository(db_session)
    prices = list(reversed(price_repo.get_for_symbol("NVDA")))
    bars = [
        {"timestamp": p.timestamp.isoformat(), "open": p.open, "high": p.high, "low": p.low, "close": p.close, "volume": p.volume}
        for p in prices
    ]
    report = build_research_report("NVDA", bars, [])
    interpretation, source = narrator.interpret(report)
    report = report.model_copy(update={"interpretation": interpretation, "interpretation_source": source})

    # Execute BUY
    exec1 = trading_agent.execute(report, idempotency_key="loss-test-1")
    assert exec1["status"] == "FILLED"

    # Now add downward trend data to generate SELL signal at low price
    # Add more bars with downward trend (price dropping to ~40)
    stock = StockRepository(db_session).get_by_symbol("NVDA")
    from app.database.models import HistoricalPrice
    from datetime import datetime, timezone
    import pandas as pd
    # Add 10 more bars going down from ~160 to ~40
    # Use timestamps without microseconds to match existing format
    dates = pd.date_range("2025-03-02", periods=10, freq="D", tz="UTC")
    for i, ts in enumerate(dates):
        price = 160 - i * 12  # Goes from 160 to ~40
        new_bar = HistoricalPrice(
            stock_id=stock.id,
            timestamp=ts.to_pydatetime(),
            open=price,
            high=price + 1,
            low=price - 1,
            close=price,
            volume=100_000,
            source="test",
        )
        HistoricalPriceRepository(db_session).create_or_update(new_bar)
    db_session.commit()

    # Generate new research report with SELL signal
    prices = list(reversed(price_repo.get_for_symbol("NVDA")))
    bars = [
        {"timestamp": p.timestamp.isoformat(), "open": p.open, "high": p.high, "low": p.low, "close": p.close, "volume": p.volume}
        for p in prices
    ]
    loss_report = build_research_report("NVDA", bars, [])
    interpretation, source = narrator.interpret(loss_report)
    loss_report = loss_report.model_copy(update={"interpretation": interpretation, "interpretation_source": source})

    assert loss_report.signal == TradeSignal.SELL

    # Execute SELL at low price to realize large loss
    exec2 = trading_agent.execute(loss_report, idempotency_key="loss-test-2")
    assert exec2["status"] == "FILLED"
    assert exec2["realized_pnl"] < Decimal("-500")

    # Now try to BUY again - should be blocked by daily loss limit
    # Create fresh upward trend data for BUY signal
    add_stock_and_bars(db_session, ticker="NVDA2", count=60, start_price=100, trend="up")
    db_session.commit()

    price_repo2 = HistoricalPriceRepository(db_session)
    prices2 = list(reversed(price_repo2.get_for_symbol("NVDA2")))
    bars2 = [
        {"timestamp": p.timestamp.isoformat(), "open": p.open, "high": p.high, "low": p.low, "close": p.close, "volume": p.volume}
        for p in prices2
    ]
    buy_report = build_research_report("NVDA2", bars2, [])
    interpretation, source = narrator.interpret(buy_report)
    buy_report = buy_report.model_copy(update={"interpretation": interpretation, "interpretation_source": source})

    exec3 = trading_agent.execute(buy_report, idempotency_key="loss-test-3")
    assert exec3["status"] == "REJECTED"
    assert "daily loss limit" in exec3["message"].lower()


def test_insufficient_data_signal(db_session):
    """Test that insufficient history returns INSUFFICIENT_DATA."""
    add_stock_and_bars(db_session, ticker="META", count=10, start_price=100)

    _, trading_agent, _ = make_trader_and_agents(db_session)

    price_repo = HistoricalPriceRepository(db_session)
    prices = price_repo.get_latest("META", limit=10)
    bars = [
        {"timestamp": p.timestamp.isoformat(), "open": p.open, "high": p.high, "low": p.low, "close": p.close, "volume": p.volume}
        for p in prices
    ]

    report = build_research_report("META", bars, [])
    interpretation, source = ResearchNarrator(None, "gpt-6.2-sol").interpret(report)
    report = report.model_copy(update={"interpretation": interpretation, "interpretation_source": source})

    assert report.signal == TradeSignal.INSUFFICIENT_DATA
    execution = trading_agent.execute(report, idempotency_key="insuff-test")
    assert execution["status"] == "SKIPPED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])