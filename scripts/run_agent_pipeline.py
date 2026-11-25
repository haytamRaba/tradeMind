#!/usr/bin/env python
"""Runnable agent pipeline demonstrating full flow: data -> research -> trading.
Uses SQLite in-memory database for demonstration (no PostgreSQL required).
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from decimal import Decimal
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.models import Base, HistoricalPrice, Stock
from app.database.repositories import HistoricalPriceRepository, StockRepository
from app.agents.research_agent.graph import ResearchAgent
from app.agents.trading_agent.graph import TradingAgent
from app.agents.shared.llm import ResearchNarrator
from app.execution.paper_trading import PaperTradingService
from app.market_data.providers.yahoo import YahooFinanceProvider
from app.market_data.service import MarketDataService
from app.strategies.base import TradeSignal


def create_demo_session() -> Session:
    """Create an in-memory SQLite database session with tables created."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(bind=engine, autoflush=False, expire_on_commit=False)
    return session


def seed_demo_data(session: Session, ticker: str = "MSFT", bars_count: int = 60):
    """Seed the database with demo market data for the given ticker."""
    # Create stock
    stock_repo = StockRepository(session)
    stock = stock_repo.create_or_get(
        ticker,
        name=ticker,
        exchange="NASDAQ",
        sector="Technology",
        currency="USD",
        country="US",
    )

    # Create historical price bars - upward trend to trigger BUY signals
    index = pd.date_range("2025-01-01", periods=bars_count, freq="D", tz="UTC")
    bars = [
        HistoricalPrice(
            stock_id=stock.id,
            timestamp=timestamp,
            open=100 + offset,
            high=101 + offset,
            low=99 + offset,
            close=100 + offset,
            volume=100_000,
            source="demo",
        )
        for offset, timestamp in enumerate(index)
    ]

    price_repo = HistoricalPriceRepository(session)
    price_repo.create_or_update_all(bars)
    session.commit()

    print(f"   Seeded {len(bars)} demo bars for {ticker}")
    return stock


def run_pipeline(ticker: str = "MSFT", period: str = "1mo", interval: str = "1d"):
    """Run the full agent pipeline: fetch data -> research -> execute paper trade."""
    print(f"\n{'='*60}")
    print(f"TRADEMIND AGENT PIPELINE: {ticker}")
    print(f"{'='*60}\n")

    # Create database session with demo data
    session = create_demo_session()
    try:
        # Seed demo data first
        print("1. Seeding demo market data...")
        seed_demo_data(session, ticker, bars_count=60)

        settings = Settings(paper_initial_cash=100_000)

        # Initialize services
        print("2. Initializing market data service...")
        market_data = MarketDataService(
            provider=YahooFinanceProvider(),
            session=session
        )

        print("3. Initializing research agent...")
        narrator = ResearchNarrator(None, "gpt-6.2-sol")  # No API key = deterministic
        research_agent = ResearchAgent(market_data=market_data, narrator=narrator)

        print("4. Initializing trading agent...")
        paper_trading = PaperTradingService(session, settings=settings)
        trading_agent = TradingAgent(paper_trading=paper_trading, market_data=market_data)

        # Step 1: Fetch and store market data (using demo data we seeded)
        print(f"\n5. Running research agent for {ticker}...")
        # We use the seeded data directly by calling the research nodes
        from app.agents.research_agent.nodes import build_research_report

        # Get the data from our seeded database
        price_repo = HistoricalPriceRepository(session)
        stock_repo = StockRepository(session)
        stock = stock_repo.get_by_symbol(ticker)
        prices = price_repo.get_latest(stock.symbol, limit=60)

        # Convert to bars format
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

        # Build research report directly from seeded data
        report = build_research_report(ticker, bars, [])
        interpretation, source = narrator.interpret(report)
        report = report.model_copy(
            update={"interpretation": interpretation, "interpretation_source": source}
        )

        print(f"   Signal: {report.signal.value}")
        print(f"   Latest Price: ${report.latest_price:.2f}")
        print(f"   Stop Loss: ${report.proposed_stop_loss:.2f}" if report.proposed_stop_loss else "   Stop Loss: N/A")
        print(f"   Take Profit: ${report.proposed_take_profit:.2f}" if report.proposed_take_profit else "   Take Profit: N/A")
        print(f"   Strategies Evaluated: {len(report.decision.strategies)}")
        for strat in report.decision.strategies:
            print(f"     - {strat.strategy}: {strat.signal.value} (evidence: {strat.evidence})")

        # Step 2: Execute paper trade (if signal is BUY or SELL)
        execution = None
        if report.signal.value in ("BUY", "SELL"):
            print(f"\n6. Executing paper trade for {ticker}...")
            execution = trading_agent.execute(report, idempotency_key=f"demo-{ticker}-{period}")
            print(f"   Order ID: {execution['order_id']}")
            print(f"   Status: {execution['status']}")
            print(f"   Side: {execution['side']}")
            print(f"   Quantity: {execution['quantity']}")
            print(f"   Execution Price: ${execution['execution_price']}")
            print(f"   Message: {execution['message']}")
        else:
            print(f"\n6. Signal is {report.signal.value} - no trade executed")

        # Step 3: Show portfolio
        print(f"\n7. Current portfolio state:")
        portfolio = trading_agent.get_portfolio()
        print(f"   Cash: ${portfolio['cash']}")
        print(f"   Equity: ${portfolio['equity']}")
        print(f"   Positions: {len(portfolio['positions'])}")
        for pos in portfolio["positions"]:
            print(f"     - {pos['ticker']}: {pos['quantity']} @ ${pos['average_entry_price']}")

        # Step 4: Monitor positions
        print(f"\n8. Monitoring protective levels...")
        monitor_result = trading_agent.monitor_positions()
        print(f"   Refreshed: {monitor_result['refreshed']}")
        print(f"   Errors: {monitor_result['errors']}")
        print(f"   Exits triggered: {len(monitor_result['exits'])}")
        for exit in monitor_result["exits"]:
            print(f"     - {exit['ticker']}: {exit['message']}")

        # Step 5: Show orders
        print(f"\n9. Order history:")
        orders = trading_agent.get_orders(limit=10)
        for order in orders:
            print(f"   #{order['order_id']}: {order['side']} {order['quantity']} {order['ticker']} @ ${order['execution_price']} - {order['status']}")

        print(f"\n{'='*60}")
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print(f"{'='*60}\n")

        return {
            "fetched_bars": len(bars),
            "signal": report.signal.value,
            "execution": execution,
            "portfolio": portfolio,
            "monitor_result": monitor_result,
            "orders": orders,
        }

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run TradeMind agent pipeline (demo with SQLite)")
    parser.add_argument("--ticker", default="MSFT", help="Ticker symbol")
    parser.add_argument("--period", default="1mo", help="Period (unused in demo)")
    parser.add_argument("--interval", default="1d", help="Interval (unused in demo)")
    args = parser.parse_args()

    result = run_pipeline(args.ticker, args.period, args.interval)

    # Save result to actions_demo.txt
    output_file = PROJECT_ROOT / "actions_demo.txt"
    with open(output_file, "w") as f:
        f.write(f"TradeMind Agent Pipeline Demo\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Ticker: {args.ticker}\n")
        f.write(f"Period: {args.period}\n")
        f.write(f"Interval: {args.interval}\n")
        f.write(f"{'='*60}\n\n")
        f.write(json.dumps(result, indent=2, default=str))

    print(f"\nResult saved to: {output_file}")
    sys.exit(0 if "error" not in result else 1)