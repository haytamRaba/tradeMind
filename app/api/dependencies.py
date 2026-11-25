"""FastAPI dependencies for market data routes."""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.agents.research_agent.graph import ResearchAgent
from app.agents.shared.llm import ResearchNarrator
from app.agents.trading_agent.graph import TradingAgent
from app.config import get_settings
from app.database.session import get_db
from app.execution.paper_trading import PaperTradingService
from app.market_data.providers.yahoo import YahooFinanceProvider
from app.market_data.service import MarketDataService


def get_market_data_service(
    session: Session = Depends(get_db),
) -> Generator[MarketDataService, None, None]:
    yield MarketDataService(provider=YahooFinanceProvider(), session=session)


def get_research_agent(
    market_data: MarketDataService = Depends(get_market_data_service),
) -> ResearchAgent:
    settings = get_settings()
    narrator = ResearchNarrator(settings.openai_api_key, settings.openai_model)
    return ResearchAgent(market_data=market_data, narrator=narrator)


def get_trading_agent(
    session: Session = Depends(get_db),
    market_data: MarketDataService = Depends(get_market_data_service),
) -> TradingAgent:
    return TradingAgent(
        paper_trading=PaperTradingService(session),
        market_data=market_data,
    )
