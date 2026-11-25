"""TradeMind market-data API application."""

from fastapi import FastAPI

from app.api.routes.market_data import router
from app.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.project_name, version="0.1.0")
app.include_router(router, prefix=settings.api_v1_prefix)
