"""Trading agent that submits research signals to the paper broker only."""

from __future__ import annotations

from typing import Any

from app.agents.research_agent.schemas import ResearchReport
from app.execution.paper_trading import PaperTradingService
from app.market_data.service import MarketDataService
from app.strategies.base import TradeSignal


class TradingAgent:
    """Keep research decisions, risk checks, and simulated execution separate."""

    def __init__(
        self,
        paper_trading: PaperTradingService,
        market_data: MarketDataService,
    ) -> None:
        self.paper_trading = paper_trading
        self.market_data = market_data

    def execute(
        self, report: ResearchReport, *, idempotency_key: str
    ) -> dict[str, Any]:
        if report.signal != report.decision.signal:
            raise ValueError("Research signal does not match its strategy decision")
        return self.paper_trading.execute(
            ticker=report.ticker,
            signal=report.signal,
            entry_price=report.latest_price,
            stop_loss=report.proposed_stop_loss,
            take_profit=report.proposed_take_profit,
            idempotency_key=idempotency_key,
        )

    def monitor_positions(self) -> dict[str, Any]:
        portfolio = self.paper_trading.get_portfolio()
        refreshed = []
        errors = []
        for position in portfolio["positions"]:
            ticker = position["ticker"]
            try:
                self.market_data.fetch_latest_and_store(ticker)
                refreshed.append(ticker)
            except Exception as exc:
                errors.append({"ticker": ticker, "message": str(exc)})
        exits = self.paper_trading.monitor_protective_levels(
            skip_tickers={item["ticker"] for item in errors}
        )
        return {"refreshed": refreshed, "errors": errors, "exits": exits}

    def get_portfolio(self) -> dict[str, Any]:
        return self.paper_trading.get_portfolio()

    def get_orders(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.paper_trading.get_orders(limit)
