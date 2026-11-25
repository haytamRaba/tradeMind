"""Data-access layer: repository implementations over SQLAlchemy 2.0.

The repository layer owns everything about *how* rows are read and written.
It knows about SQLAlchemy, sessions, and the composite unique constraint on
``(stock_id, timestamp)`` -- but it knows nothing about HTTP, validation, or
the provider.  The service layer sits between the repository and the API and
delegates persistence to it.

Idempotent upsert
-----------------
PostgreSQL rows are inserted with
``INSERT ... ON CONFLICT (stock_id, timestamp) DO UPDATE ...``.  Because the
unique constraint ``uq_stock_timestamp`` exists, repeating a fetch against the
same stock and window replaces the bars in place instead of multiplying them.
The repository exposes two primitives:

* ``create_or_update``  -- one bar at a time (used by the batch service).
* ``create_or_update_all`` -- a single bulk UPSERT for many bars.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .models import HistoricalPrice, Stock

class StockRepository:
    """CRUD for ``stocks``."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_symbol(self, symbol: str) -> Stock | None:
        """Return the stock whose normalized symbol matches ``symbol``."""
        return self.session.scalar(select(Stock).where(Stock.symbol == symbol.upper()))

    def create_or_get(self, symbol: str, **payload: Any) -> Stock:
        """Insert a stock if absent, otherwise return the existing row.

        The unique constraint on ``symbol`` makes this idempotent: a second call
        with the same symbol does not create a duplicate.
        """
        symbol = symbol.upper()
        bind = self.session.get_bind()
        insert = sqlite_insert if bind.dialect.name == "sqlite" else pg_insert
        stmt = insert(Stock).values(symbol=symbol, **payload)
        self.session.execute(stmt.on_conflict_do_nothing(index_elements=["symbol"]))
        self.session.flush()
        stock = self.get_by_symbol(symbol)
        if stock is None:
            raise RuntimeError(f"Stock '{symbol}' could not be inserted or retrieved")
        return stock

    def list_all(self) -> list[Stock]:
        """Return every stock row, oldest first (by symbol)."""
        return self.session.scalars(select(Stock).order_by(Stock.symbol)).all()


class HistoricalPriceRepository:
    """CRUD + idempotent upsert for ``historical_prices``."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Single-row helpers
    # ------------------------------------------------------------------
    def create_or_update(self, row: HistoricalPrice) -> HistoricalPrice:
        """Insert a single bar, replacing an existing bar for the same stock
        and timestamp (idempotent means no duplicate on re-fetch)."""
        self.create_or_update_all([row])
        stored = self.session.scalar(
            select(HistoricalPrice).where(
                HistoricalPrice.stock_id == row.stock_id,
                HistoricalPrice.timestamp == row.timestamp,
            )
        )
        if stored is None:
            raise RuntimeError("Historical price was not available after the upsert")
        return stored

    # ------------------------------------------------------------------
    # Bulk helpers
    # ------------------------------------------------------------------
    def create_or_update_all(self, rows: list[HistoricalPrice]) -> None:
        """Build the composite unique constraint into a single upsert."""

        if not rows:
            return

        now = datetime.now(timezone.utc)
        payloads = []
        for r in rows:
            if r.created_at is None:
                # ORM-level defaults are bypassed by the bulk insert, so we
                # stamp this here to keep the column non-null for every driver.
                r.created_at = now
            payloads.append(
                {
                    "stock_id": r.stock_id,
                    "timestamp": r.timestamp,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                    "source": r.source,
                    "created_at": r.created_at,
                }
            )

        bind = self.session.get_bind()
        insert = sqlite_insert if bind.dialect.name == "sqlite" else pg_insert
        insert_stmt = insert(HistoricalPrice).values(payloads)
        excluded = insert_stmt.excluded
        stmt = insert_stmt.on_conflict_do_update(
                index_elements=["stock_id", "timestamp"],
                set_={
                    "open": excluded.open,
                    "high": excluded.high,
                    "low": excluded.low,
                    "close": excluded.close,
                    "volume": excluded.volume,
                    "source": excluded.source,
                    "created_at": excluded.created_at,
                },
            )
        self.session.execute(stmt)
        self.session.flush()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def get_latest(self, stock_symbol: str, *, limit: int = 1) -> list[HistoricalPrice]:
        """Return the newest bars for a symbol (joined to ``stocks``).

        The join keeps the repository coupled to a business key (``symbol``)
        instead of the internal ``stock_id``, which makes the service layer's
        job trivial.
        """
        stmt = (
            select(HistoricalPrice)
            .join(Stock, Stock.id == HistoricalPrice.stock_id)
            .where(Stock.symbol == stock_symbol)
            .order_by(HistoricalPrice.timestamp.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def get_for_symbol(
        self, stock_symbol: str, *, start: Any = None, end: Any = None
    ) -> list[HistoricalPrice]:
        """Return all bars for a symbol in an optional closed UTC window."""
        stmt = select(HistoricalPrice).join(Stock).where(Stock.symbol == stock_symbol)
        if start is not None:
            stmt = stmt.where(HistoricalPrice.timestamp >= start)
        if end is not None:
            stmt = stmt.where(HistoricalPrice.timestamp <= end)
        stmt = stmt.order_by(HistoricalPrice.timestamp.asc())
        return list(self.session.scalars(stmt))

    def count_for_symbol(self, stock_symbol: str) -> int:
        """Count how many bars are stored for a symbol."""
        stmt = (
            sa.select(sa.func.count(HistoricalPrice.id))
            .join(Stock, Stock.id == HistoricalPrice.stock_id)
            .where(Stock.symbol == stock_symbol)
        )
        return self.session.scalar(stmt) or 0
