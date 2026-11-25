"""Research agent orchestration for market-data retrieval and analysis."""

from __future__ import annotations

from app.agents.research_agent.nodes import build_research_report
from app.agents.research_agent.schemas import ResearchReport
from app.agents.shared.llm import ResearchNarrator
from app.market_data.service import MarketDataService


class ResearchAgent:
    """Fetch validated history, evaluate strategies, and explain the evidence."""

    def __init__(
        self,
        market_data: MarketDataService,
        narrator: ResearchNarrator,
    ) -> None:
        self.market_data = market_data
        self.narrator = narrator

    def run(
        self, ticker: str, *, period: str = "6mo", interval: str = "1d"
    ) -> ResearchReport:
        fetched = self.market_data.fetch_and_store(
            ticker, period=period, interval=interval
        )
        report = build_research_report(
            ticker,
            fetched["data"],
            fetched["issues"],
        )
        interpretation, source = self.narrator.interpret(report)
        return report.model_copy(
            update={"interpretation": interpretation, "interpretation_source": source}
        )
