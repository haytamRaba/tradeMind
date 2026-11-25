"""Research-agent and paper-trading endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.research_agent.graph import ResearchAgent
from app.agents.research_agent.schemas import ResearchReport
from app.agents.trading_agent.graph import TradingAgent
from app.agents.trading_agent.schemas import (
    PaperOrderResponse,
    PaperPortfolioResponse,
    ProtectiveMonitorResponse,
    TradeExecutionRequest,
)
from app.api.dependencies import get_research_agent, get_trading_agent
from app.api.routes.market_data import _raise_market_data_error
from app.api.schemas.agents import TradingRunResponse

router = APIRouter()


@router.post(
    "/agents/research/{ticker}",
    response_model=ResearchReport,
    tags=["agents"],
)
def run_research(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    agent: ResearchAgent = Depends(get_research_agent),
) -> ResearchReport:
    try:
        return agent.run(ticker, period=period, interval=interval)
    except Exception as exc:
        _raise_market_data_error(exc)


@router.post(
    "/agents/trading/{ticker}/execute",
    response_model=TradingRunResponse,
    tags=["agents"],
)
def run_trading_agent(
    ticker: str,
    request: TradeExecutionRequest,
    research_agent: ResearchAgent = Depends(get_research_agent),
    trading_agent: TradingAgent = Depends(get_trading_agent),
) -> dict:
    try:
        report = research_agent.run(ticker)
        execution = trading_agent.execute(report, idempotency_key=request.idempotency_key)
        return {"research": report, "execution": execution}
    except Exception as exc:
        _raise_market_data_error(exc)


@router.get(
    "/paper-trading/portfolio",
    response_model=PaperPortfolioResponse,
    tags=["paper trading"],
)
def get_paper_portfolio(
    agent: TradingAgent = Depends(get_trading_agent),
) -> dict:
    return agent.get_portfolio()


@router.get(
    "/paper-trading/orders",
    response_model=list[PaperOrderResponse],
    tags=["paper trading"],
)
def get_paper_orders(
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    agent: TradingAgent = Depends(get_trading_agent),
) -> list[dict]:
    return agent.get_orders(limit)


@router.post(
    "/paper-trading/monitor",
    response_model=ProtectiveMonitorResponse,
    tags=["paper trading"],
)
def monitor_paper_positions(
    agent: TradingAgent = Depends(get_trading_agent),
) -> dict:
    return agent.monitor_positions()
