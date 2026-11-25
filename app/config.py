"""Centralized application configuration.

TradeMind loads its settings from a ``.env`` file (and, failing that, from the
process environment).  ``Settings`` is a pydantic ``BaseSettings`` so that every
field can be overridden by environment variables or ``.env``.

Why pydantic-settings?
    * Type coercion happens once, at load time (``DB_PORT`` becomes an ``int``).
    * A single point of truth: every module imports ``get_settings()`` and never
      touches ``os.getenv`` directly.
    * Testability: ``Settings`` is a plain data class, so tests instantiate it
      with overrides instead of monkeypatching ``os.getenv``.

Architecture note
    Configuration lives here and nowhere else in the application.  The
    ``app/database`` layer and the ``app/api`` layer both depend on this module
    and on nothing lower, which keeps the dependency graph acyclic.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from sqlalchemy.engine import URL

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the project root independent of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Central configuration for the TradeMind API and its tasks."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # ------------------------------------------------------------------ API
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    """Host the ASGI server binds to. ``0.0.0.0`` inside Docker."""
    app_port: int = Field(default=8000, validation_alias="APP_PORT")
    """Port the ASGI server listens on."""
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    """Environment name (``development`` / ``production``)."""
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    """Python logging level for the application root logger."""

    # ------------------------------------------------------------- PostgreSQL
    # ``DB_HOST`` is injected by ``docker-compose.yml``; it is omitted here so
    # it can only be supplied through the compose file or a local ``.env``.
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_user: str = Field(default="trademind", validation_alias="DB_USER")
    db_password: str = Field(default="change-me", validation_alias="DB_PASSWORD")
    db_name: str = Field(default="trademind", validation_alias="DB_NAME")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")

    # Connection pool settings
    db_pool_size: int = Field(default=5, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, validation_alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, validation_alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=3600, validation_alias="DB_POOL_RECYCLE")

    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-6.2-sol", validation_alias="OPENAI_MODEL")

    paper_initial_cash: float = Field(default=100_000, validation_alias="PAPER_INITIAL_CASH")
    max_risk_per_trade_pct: float = Field(default=0.01, validation_alias="MAX_RISK_PER_TRADE_PCT")
    max_position_pct: float = Field(default=0.10, validation_alias="MAX_POSITION_PCT")
    max_portfolio_exposure_pct: float = Field(default=0.50, validation_alias="MAX_PORTFOLIO_EXPOSURE_PCT")
    max_daily_loss_pct: float = Field(default=0.05, validation_alias="MAX_DAILY_LOSS_PCT")
    max_open_positions: int = Field(default=10, validation_alias="MAX_OPEN_POSITIONS")

    @property
    def database_url(self) -> str:
        """Build the PostgreSQL connection URL from the configured fields."""
        if self.database_url_override:
            return self.database_url_override
        return URL.create(
            "postgresql+psycopg2",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)

    @property
    def database_url_sync(self) -> str:
        """Same URL without the ``+psycopg2`` driver suffix for raw drivers."""
        return self.database_url.replace("+psycopg2", "", 1)

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        value = value.upper()
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if value not in valid:
            raise ValueError(f"log_level must be one of {sorted(valid)}")
        return value

    @field_validator("paper_initial_cash")
    @classmethod
    def _validate_initial_cash(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Paper trading initial cash must be positive")
        return value

    @field_validator(
        "max_risk_per_trade_pct",
        "max_position_pct",
        "max_portfolio_exposure_pct",
        "max_daily_loss_pct",
    )
    @classmethod
    def _validate_positive_risk_settings(cls, value: float) -> float:
        if value <= 0 or value > 1:
            raise ValueError("Risk percentages must be greater than zero and at most one")
        return value

    @field_validator("max_open_positions")
    @classmethod
    def _validate_position_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_open_positions must be at least one")
        return value

    # ------------------------------------------------------------- metadata
    project_name: str = Field(default="TradeMind", validation_alias="PROJECT_NAME")
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide application settings."""
    return Settings()
