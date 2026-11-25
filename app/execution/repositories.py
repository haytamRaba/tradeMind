"""Persistence helpers for the single simulated trading account."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.database.models import PaperOrder, PaperPortfolio, PaperPosition, Stock


class PaperPortfolioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_default(self, initial_cash: Decimal) -> PaperPortfolio:
        """Create the paper account once, then lock it for order updates."""
        existing = self.session.scalar(
            select(PaperPortfolio)
            .where(PaperPortfolio.name == "default")
            .with_for_update()
        )
        if existing is None:
            insert = sqlite_insert if self.session.get_bind().dialect.name == "sqlite" else postgres_insert
            self.session.execute(
                insert(PaperPortfolio)
                .values(name="default", starting_cash=initial_cash, cash=initial_cash)
                .on_conflict_do_nothing(index_elements=["name"])
            )
            self.session.flush()
            existing = self.session.scalar(
                select(PaperPortfolio)
                .where(PaperPortfolio.name == "default")
                .with_for_update()
            )
        if existing is None:
            raise RuntimeError("Default paper portfolio could not be created")
        return existing

    def positions(self, portfolio_id: int) -> list[tuple[PaperPosition, Stock]]:
        return list(
            self.session.execute(
                select(PaperPosition, Stock)
                .join(Stock, Stock.id == PaperPosition.stock_id)
                .where(PaperPosition.portfolio_id == portfolio_id)
            ).all()
        )

    def position(self, portfolio_id: int, stock_id: int) -> PaperPosition | None:
        return self.session.scalar(
            select(PaperPosition)
            .where(
                PaperPosition.portfolio_id == portfolio_id,
                PaperPosition.stock_id == stock_id,
            )
            .with_for_update()
        )


class PaperOrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_key(self, key: str) -> PaperOrder | None:
        return self.session.scalar(
            select(PaperOrder).where(PaperOrder.idempotency_key == key)
        )

    def add(self, order: PaperOrder) -> PaperOrder:
        self.session.add(order)
        self.session.flush()
        return order

    def realized_pnl_today(self, portfolio_id: int) -> Decimal:
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        value = self.session.scalar(
            select(func.coalesce(func.sum(PaperOrder.realized_pnl), 0)).where(
                PaperOrder.portfolio_id == portfolio_id,
                PaperOrder.status == "FILLED",
                PaperOrder.created_at >= start,
            )
        )
        return Decimal(str(value or 0))

    def list_recent(self, portfolio_id: int, limit: int = 100) -> list[PaperOrder]:
        return list(
            self.session.scalars(
                select(PaperOrder)
                .where(PaperOrder.portfolio_id == portfolio_id)
                .order_by(PaperOrder.created_at.desc(), PaperOrder.id.desc())
                .limit(limit)
            )
        )
