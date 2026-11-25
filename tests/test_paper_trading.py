from datetime import datetime, timezone
from decimal import Decimal

from app.config import Settings
from app.database.models import HistoricalPrice
from app.database.repositories import HistoricalPriceRepository, StockRepository
from app.execution.paper_trading import PaperTradingService
from app.strategies.base import TradeSignal


def add_stock_and_bar(session, *, ticker="MSFT", timestamp=None, price=100):
    stock = StockRepository(session).create_or_get(
        ticker,
        name=ticker,
        exchange="TEST",
        sector="Technology",
        currency="USD",
        country="US",
    )
    timestamp = timestamp or datetime(2025, 1, 1, tzinfo=timezone.utc)
    bar = HistoricalPrice(
        stock_id=stock.id,
        timestamp=timestamp,
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=100_000,
        source="test",
    )
    HistoricalPriceRepository(session).create_or_update_all([bar])
    return stock


def service(session, **overrides):
    settings = Settings(paper_initial_cash=10_000, **overrides)
    return PaperTradingService(session, settings=settings)


def buy(trader, key="buy-1"):
    return trader.execute(
        ticker="MSFT",
        signal=TradeSignal.BUY,
        entry_price=100,
        stop_loss=90,
        take_profit=130,
        idempotency_key=key,
    )


def test_paper_buy_sizes_position_and_replays_idempotently(db_session):
    add_stock_and_bar(db_session)
    trader = service(db_session)
    order = buy(trader)
    replay = buy(trader)
    portfolio = trader.get_portfolio()

    assert order["status"] == "FILLED"
    assert order["quantity"] == Decimal("10.00000000")
    assert replay["replayed"] is True
    assert replay["order_id"] == order["order_id"]
    assert portfolio["cash"] == Decimal("9000.0000")
    assert portfolio["positions"][0]["stop_loss"] == Decimal("90.00000000")


def test_paper_sell_closes_position_and_records_realized_pnl(db_session):
    add_stock_and_bar(db_session)
    trader = service(db_session)
    buy(trader)
    sell = trader.execute(
        ticker="MSFT",
        signal=TradeSignal.SELL,
        entry_price=120,
        stop_loss=None,
        take_profit=None,
        idempotency_key="sell-1",
    )

    assert sell["status"] == "FILLED"
    assert sell["realized_pnl"] == Decimal("200.0000")
    assert trader.get_portfolio()["positions"] == []
    assert trader.get_portfolio()["cash"] == Decimal("10200.0000")


def test_buy_without_stop_loss_is_persistently_rejected(db_session):
    add_stock_and_bar(db_session)
    result = service(db_session).execute(
        ticker="MSFT",
        signal=TradeSignal.BUY,
        entry_price=100,
        stop_loss=None,
        take_profit=None,
        idempotency_key="missing-stop",
    )
    assert result["status"] == "REJECTED"
    assert "stop loss" in result["message"].lower()


def test_daily_loss_limit_blocks_new_buys_but_keeps_audit(db_session):
    add_stock_and_bar(db_session)
    trader = service(db_session)
    buy(trader)
    trader.execute(
        ticker="MSFT",
        signal=TradeSignal.SELL,
        entry_price=40,
        stop_loss=None,
        take_profit=None,
        idempotency_key="large-loss",
    )
    rejected = buy(trader, key="after-loss")
    assert rejected["status"] == "REJECTED"
    assert "daily loss limit" in rejected["message"].lower()


def test_protective_stop_closes_position_at_latest_stored_bar(db_session):
    add_stock_and_bar(db_session)
    trader = service(db_session)
    buy(trader)
    add_stock_and_bar(
        db_session,
        timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc),
        price=88,
    )

    exits = trader.monitor_protective_levels()

    assert len(exits) == 1
    assert "stop crossed" in exits[0]["message"].lower()
    assert trader.get_portfolio()["positions"] == []
