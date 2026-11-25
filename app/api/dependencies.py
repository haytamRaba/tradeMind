"""FastAPI dependencies for market data routes."""

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.market_data.providers.yahoo import YahooFinanceProvider
from app.market_data.service import MarketDataService


def get_market_data_service(
    session: Session = Depends(get_db),
) -> Generator[MarketDataService, None, None]:
    yield MarketDataService(provider=YahooFinanceProvider(), session=session)
