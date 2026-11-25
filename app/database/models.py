"""Database models for stocks and historical market prices.

Each stock has one normalized ticker symbol. Historical prices are unique by
stock and timestamp, so fetching the same bar again updates its existing row.
All stored timestamps use UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, MetaData, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column as mc
from sqlalchemy.types import BigInteger, DateTime, Float, Integer, Numeric, String, Text, TypeDecorator

# SQLAlchemy uses this naming convention when it creates constraints.


class DateTimeUTC(TypeDecorator):  # noqa: D401
    """Timezone-aware ``DateTime`` that accepts strings as a convenience.

    ``psycopg2`` (the production driver) accepts ISO-8601 strings, but SQLite's
    heritage of the test harness requires native ``datetime`` objects.  This
    decorator normalises whatever is handed to it into a UTC-aware ``datetime``
    before it ever reaches the dialect, so the rest of the model does not have
    to think about the difference.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> datetime | None:  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("timestamp values must be datetime objects or ISO strings")
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:  # type: ignore[override]
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

# ``Alembic`` + ``SQLAlchemy`` both rely on a consistent naming scheme for
# constraints so that generated migrations are stable across renames.  The
# convention is the one recommended in the SQLAlchemy docs.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = metadata


class Stock(Base):
    """A recognized ticker and its metadata."""

    __tablename__ = "stocks"

    id: Mapped[int] = mc(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mc(String(12), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mc(String(128), nullable=False)
    exchange: Mapped[str | None] = mc(String(16), nullable=False)
    sector: Mapped[str | None] = mc(String(64), nullable=False)
    market_cap: Mapped[float | None] = mc(Float, nullable=True)
    currency: Mapped[str | None] = mc(String(3), nullable=False)
    country: Mapped[str | None] = mc(String(32), nullable=False)
    update_at: Mapped[datetime] = mc(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # --- repository handles -----------------------------------------
    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Stock(symbol={self.symbol!r}, name={self.name!r})>"


class HistoricalPrice(Base):
    """A single OHLCV bar for a ticker, normalized to UTC.

    Imports: app/database/repositories.py (HistoricalPriceRepository), tests/test_market_data.py
    Exports: HistoricalPrice ORM model
    Data schema: OHLCV bars with stock_id, timestamp, open, high, low, close, volume, source
    User instruction: complete all phases in plan.md (add indexes for common query patterns)
    """

    __tablename__ = "historical_prices"

    id: Mapped[int] = mc(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mc(ForeignKey("stocks.id", ondelete="CASCADE"), index=True, nullable=False)
    timestamp: Mapped[datetime] = mc(
        DateTimeUTC(), index=True, nullable=False
    )
    open: Mapped[float] = mc(Float, nullable=False)
    high: Mapped[float] = mc(Float, nullable=False)
    low: Mapped[float] = mc(Float, nullable=False)
    close: Mapped[float] = mc(Float, nullable=False)
    volume: Mapped[int] = mc(BigInteger, nullable=False)
    source: Mapped[str] = mc(String(16), nullable=False)
    created_at: Mapped[datetime] = mc(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        # One row per (stock, timestamp) -- the idempotent-insert guarantee.
        UniqueConstraint(
            "stock_id",
            "timestamp",
            name="uq_stock_timestamp",
        ),
        CheckConstraint("open > 0 AND high > 0 AND low > 0 AND close > 0", name="positive_prices"),
        CheckConstraint(
            "low <= open AND low <= close AND open <= high AND close <= high",
            name="valid_ohlc_range",
        ),
        CheckConstraint("volume >= 0", name="non_negative_volume"),
        # Composite index for common query: get_latest(stock_symbol, limit) - stock_id + timestamp DESC
        # The unique constraint (stock_id, timestamp) serves as a composite index.
        # For explicit DESC scan optimization, PostgreSQL can scan the unique index backward.
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"<HistoricalPrice(stock_id={self.stock_id!r}, timestamp="
            f"{self.timestamp!r}, close={self.close!r})>"
        )


class PaperPortfolio(Base):
    """Single-user simulated portfolio and its available cash."""

    __tablename__ = "paper_portfolios"

    id: Mapped[int] = mc(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mc(String(48), unique=True, nullable=False)
    starting_cash: Mapped[Decimal] = mc(Numeric(20, 4), nullable=False)
    cash: Mapped[Decimal] = mc(Numeric(20, 4), nullable=False)
    created_at: Mapped[datetime] = mc(
        DateTimeUTC(), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mc(
        DateTimeUTC(), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint("starting_cash > 0", name="positive_starting_cash"),
        CheckConstraint("cash >= 0", name="non_negative_cash"),
    )


class PaperPosition(Base):
    """Open simulated position, unique per portfolio and stock."""

    __tablename__ = "paper_positions"

    id: Mapped[int] = mc(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mc(ForeignKey("paper_portfolios.id", ondelete="CASCADE"), index=True)
    stock_id: Mapped[int] = mc(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[Decimal] = mc(Numeric(20, 8), nullable=False)
    average_entry_price: Mapped[Decimal] = mc(Numeric(20, 8), nullable=False)
    stop_loss: Mapped[Decimal] = mc(Numeric(20, 8), nullable=False)
    take_profit: Mapped[Decimal | None] = mc(Numeric(20, 8), nullable=True)

    __table_args__ = (
        UniqueConstraint("portfolio_id", "stock_id", name="uq_paper_position_stock"),
        CheckConstraint("quantity > 0", name="positive_position_quantity"),
        CheckConstraint("average_entry_price > 0", name="positive_position_price"),
        CheckConstraint("stop_loss > 0", name="positive_position_stop"),
    )


class PaperOrder(Base):
    """Idempotent paper order and its simulated fill or rejection."""

    __tablename__ = "paper_orders"

    id: Mapped[int] = mc(Integer, primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mc(ForeignKey("paper_portfolios.id", ondelete="CASCADE"), index=True)
    stock_id: Mapped[int] = mc(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    idempotency_key: Mapped[str] = mc(String(64), unique=True, nullable=False)
    side: Mapped[str] = mc(String(4), nullable=False)
    status: Mapped[str] = mc(String(10), nullable=False)
    quantity: Mapped[Decimal] = mc(Numeric(20, 8), nullable=False)
    execution_price: Mapped[Decimal] = mc(Numeric(20, 8), nullable=False)
    stop_loss: Mapped[Decimal | None] = mc(Numeric(20, 8), nullable=True)
    take_profit: Mapped[Decimal | None] = mc(Numeric(20, 8), nullable=True)
    realized_pnl: Mapped[Decimal] = mc(Numeric(20, 4), nullable=False, default=Decimal("0"))
    rejection_reason: Mapped[str | None] = mc(Text, nullable=True)
    created_at: Mapped[datetime] = mc(DateTimeUTC(), index=True, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name="valid_paper_order_side"),
        CheckConstraint("status IN ('FILLED', 'REJECTED')", name="valid_paper_order_status"),
        CheckConstraint("execution_price > 0", name="positive_paper_order_price"),
        CheckConstraint("quantity >= 0", name="non_negative_paper_order_quantity"),
        CheckConstraint(
            "status = 'REJECTED' OR quantity > 0",
            name="positive_filled_order_quantity",
        ),
        CheckConstraint(
            "status = 'REJECTED' OR side = 'SELL' OR stop_loss IS NOT NULL",
            name="paper_buy_requires_stop",
        ),
    )
