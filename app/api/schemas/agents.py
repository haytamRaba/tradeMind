"""Request and response schemas for the research and trading agents."""

from pydantic import BaseModel

from app.agents.research_agent.schemas import ResearchReport
from app.agents.trading_agent.schemas import PaperOrderResponse


class TradingRunResponse(BaseModel):
    research: ResearchReport
    execution: PaperOrderResponse
