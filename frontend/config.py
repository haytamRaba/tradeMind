"""Streamlit frontend configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class FrontendSettings(BaseSettings):
    """Frontend-specific settings loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API connection
    api_base_url: str = Field(default="http://localhost:8000", validation_alias="FASTAPI_BASE_URL")
    api_timeout: int = 30

    # Streamlit config
    page_title: str = "TradeMind"
    page_icon: str = "📈"
    layout: str = "wide"

    # Cache TTL (seconds)
    cache_ttl_market_data: int = 60
    cache_ttl_research: int = 120
    cache_ttl_portfolio: int = 30


@lru_cache
def get_frontend_settings() -> FrontendSettings:
    """Return cached frontend settings."""
    return FrontendSettings()