"""Persistent, single-account paper trading with deterministic risk checks."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.models import PaperOrder, PaperPosition, Stock
from app.database.repositories import HistoricalPriceRepository, StockRepository
from app.execution.broker_interface import BrokerFill, BrokerInterface
from app.execution.repositories import PaperOrderRepository, PaperPortfolioRepository
from app.risk.limits import RiskLimits
from app.risk.position_sizing import PositionSizer
from app.risk.risk_validator import RiskRejected, RiskValidator
from app.strategies.base import TradeSignal

ZERO = Decimal("0")


class PaperBroker(BrokerInterface):
    """Simulate a complete market fill at the validated reference price."""

    def execute_market_order(
        self, *, side: str, quantity: Decimal, reference_price: Decimal
    ) -> BrokerFill:
        if side not in {"BUY", "SELL"} or quantity <= 0 or reference_price <= 0:
            raise ValueError("Paper broker received an invalid order")
        return BrokerFill(quantity=quantity, price=reference_price)


class PaperTradingService:
    """Apply paper orders to the account only after deterministic risk checks."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        broker: BrokerInterface | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.portfolios = PaperPortfolioRepository(session)
        self.orders = PaperOrderRepository(session)
        self.stocks = StockRepository(session)
        self.prices = HistoricalPriceRepository(session)
        self.broker = broker or PaperBroker()
        self.risk = RiskValidator(RiskLimits.from_settings(self.settings), PositionSizer())

    def execute(
        self,
        *,
        ticker: str,
        signal: TradeSignal,
        entry_price: float,
        stop_loss: float | None,
        take_profit: float | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        symbol = ticker.strip().upper()
        side = signal.value
        if side not in {TradeSignal.BUY.value, TradeSignal.SELL.value}:
            return {
                "ticker": symbol,
                "side": side,
                "status": "SKIPPED",
                "quantity": ZERO,
                "execution_price": Decimal(str(entry_price)),
                "realized_pnl": ZERO,
                "idempotency_key": idempotency_key,
                "message": "Only BUY or SELL research signals can be sent to the paper broker.",
                "replayed": False,
            }
        if not idempotency_key or len(idempotency_key) > 64:
            raise ValueError("idempotency_key must contain between 1 and 64 characters")
        price = Decimal(str(entry_price))
        stop = Decimal(str(stop_loss)) if stop_loss is not None else None
        target = Decimal(str(take_profit)) if take_profit is not None else None
        if price <= 0:
            raise ValueError("Entry price must be positive")

        account = self.portfolios.get_default(Decimal(str(self.settings.paper_initial_cash)))
        stock = self.stocks.get_by_symbol(symbol)
        if stock is None:
            raise ValueError(f"No stored market data exists for '{symbol}'")
        prior = self.orders.get_by_key(idempotency_key)
        if prior is not None:
            if (
                prior.stock_id != stock.id
                or prior.side != side
                or prior.stop_loss != stop
                or prior.take_profit != target
            ):
                raise ValueError("idempotency_key was already used for a different order")
            return self._serialize_order(prior, symbol, account.cash, replayed=True)

        positions = self.portfolios.positions(account.id)
        position = next((item for item, linked_stock in positions if linked_stock.id == stock.id), None)
        marks = self._position_marks(positions, symbol, price)
        equity = account.cash + sum((item["market_value"] for item in marks), ZERO)
        total_exposure = sum((item["market_value"] for item in marks), ZERO)
        current_mark = next((item for item in marks if item["ticker"] == symbol), None)
        current_value = current_mark["market_value"] if current_mark else ZERO

        if side == TradeSignal.BUY.value:
            try:
                quantity = self.risk.validate_buy(
                    equity=equity,
                    cash=account.cash,
                    entry_price=price,
                    stop_loss=stop,
                    take_profit=target,
                    position_count=len(positions),
                    already_holding=position is not None,
                    position_value=current_value,
                    total_exposure=total_exposure,
                    realized_pnl_today=self.orders.realized_pnl_today(account.id),
                )
            except RiskRejected as exc:
                rejected = self._reject(
                    account.id, stock.id, side, price, stop, target, idempotency_key, str(exc)
                )
                return self._serialize_order(rejected, symbol, account.cash)
        else:
            if position is None:
                rejected = self._reject(
                    account.id,
                    stock.id,
                    side,
                    price,
                    stop,
                    target,
                    idempotency_key,
                    "There is no open position to close.",
                )
                return self._serialize_order(rejected, symbol, account.cash)
            quantity = Decimal(position.quantity)

        fill = self.broker.execute_market_order(
            side=side, quantity=quantity, reference_price=price
        )
        realized = ZERO
        if side == TradeSignal.BUY.value:
            old_quantity = Decimal(position.quantity) if position else ZERO
            old_cost = Decimal(position.average_entry_price) if position else ZERO
            new_quantity = old_quantity + fill.quantity
            average = ((old_quantity * old_cost) + (fill.quantity * fill.price)) / new_quantity
            if position:
                position.quantity = new_quantity
                position.average_entry_price = average
                position.stop_loss = max(Decimal(position.stop_loss), stop or ZERO)
                if target is not None:
                    position.take_profit = max(
                        Decimal(position.take_profit or ZERO), target
                    )
            else:
                assert stop is not None
                self.session.add(
                    PaperPosition(
                        portfolio_id=account.id,
                        stock_id=stock.id,
                        quantity=new_quantity,
                        average_entry_price=average,
                        stop_loss=stop,
                        take_profit=target,
                    )
                )
            account.cash -= fill.quantity * fill.price + fill.fee
            stored_stop = stop
            stored_target = target
        else:
            assert position is not None
            realized = (fill.price - Decimal(position.average_entry_price)) * fill.quantity
            account.cash += fill.quantity * fill.price - fill.fee
            self.session.delete(position)
            stored_stop = None
            stored_target = None

        account.updated_at = datetime.now(timezone.utc)
        order = PaperOrder(
            portfolio_id=account.id,
            stock_id=stock.id,
            idempotency_key=idempotency_key,
            side=side,
            status="FILLED",
            quantity=fill.quantity,
            execution_price=fill.price,
            stop_loss=stored_stop,
            take_profit=stored_target,
            realized_pnl=realized,
        )
        self.orders.add(order)
        return self._serialize_order(order, symbol, account.cash)

    def get_portfolio(self) -> dict[str, Any]:
        account = self.portfolios.get_default(Decimal(str(self.settings.paper_initial_cash)))
        positions = self.portfolios.positions(account.id)
        marks = self._position_marks(positions)
        exposure = sum((item["market_value"] for item in marks), ZERO)
        unrealized = sum((item["unrealized_pnl"] for item in marks), ZERO)
        return {
            "name": account.name,
            "starting_cash": account.starting_cash,
            "cash": account.cash,
            "equity": account.cash + exposure,
            "market_exposure": exposure,
            "unrealized_pnl": unrealized,
            "realized_pnl_today": self.orders.realized_pnl_today(account.id),
            "positions": marks,
        }

    def get_orders(self, limit: int = 100) -> list[dict[str, Any]]:
        account = self.portfolios.get_default(Decimal(str(self.settings.paper_initial_cash)))
        rows = self.orders.list_recent(account.id, limit=limit)
        return [
            self._serialize_order(row, self._symbol_for_stock(row.stock_id), None)
            for row in rows
        ]

    def monitor_protective_levels(
        self, *, skip_tickers: set[str] | None = None
    ) -> list[dict[str, Any]]:
        """Close positions when the most recent stored bar crosses a level."""
        account = self.portfolios.get_default(Decimal(str(self.settings.paper_initial_cash)))
        positions = self.portfolios.positions(account.id)
        exits = []
        skipped = {ticker.upper() for ticker in (skip_tickers or set())}
        for position, stock in positions:
            if stock.symbol in skipped:
                continue
            latest = self.prices.get_latest(stock.symbol, limit=1)
            if not latest:
                continue
            price = Decimal(str(latest[0].close))
            stop = Decimal(position.stop_loss)
            target = Decimal(position.take_profit) if position.take_profit is not None else None
            reason = "Protective stop crossed by the latest stored bar." if price <= stop else None
            if reason is None and target is not None and price >= target:
                reason = "Take-profit crossed by the latest stored bar."
            if reason is None:
                continue
            timestamp = latest[0].timestamp.isoformat().replace(":", "").replace("+", "")
            result = self.execute(
                ticker=stock.symbol,
                signal=TradeSignal.SELL,
                entry_price=float(price),
                stop_loss=None,
                take_profit=None,
                idempotency_key=f"protect-{position.id}-{timestamp}"[:64],
            )
            result["message"] = reason
            exits.append(result)
        return exits

    def _position_marks(
        self,
        positions: list[tuple[PaperPosition, Any]],
        focus_ticker: str | None = None,
        focus_price: Decimal | None = None,
    ) -> list[dict[str, Any]]:
        marks = []
        for position, stock in positions:
            latest = self.prices.get_latest(stock.symbol, limit=1)
            market_price = (
                focus_price
                if focus_ticker == stock.symbol and focus_price is not None
                else Decimal(str(latest[0].close))
                if latest
                else Decimal(position.average_entry_price)
            )
            quantity = Decimal(position.quantity)
            average = Decimal(position.average_entry_price)
            marks.append(
                {
                    "ticker": stock.symbol,
                    "quantity": quantity,
                    "average_entry_price": average,
                    "stop_loss": Decimal(position.stop_loss),
                    "take_profit": Decimal(position.take_profit) if position.take_profit is not None else None,
                    "latest_price": market_price,
                    "market_value": quantity * market_price,
                    "unrealized_pnl": quantity * (market_price - average),
                }
            )
        return marks

    def _reject(
        self,
        portfolio_id: int,
        stock_id: int,
        side: str,
        price: Decimal,
        stop: Decimal | None,
        target: Decimal | None,
        key: str,
        reason: str,
    ) -> PaperOrder:
        order = PaperOrder(
            portfolio_id=portfolio_id,
            stock_id=stock_id,
            idempotency_key=key,
            side=side,
            status="REJECTED",
            quantity=ZERO,
            execution_price=price,
            stop_loss=stop,
            take_profit=target,
            realized_pnl=ZERO,
            rejection_reason=reason,
        )
        return self.orders.add(order)

    def _symbol_for_stock(self, stock_id: int) -> str:
        stock = self.session.get(Stock, stock_id)
        if stock is None:
            return "UNKNOWN"
        return stock.symbol

    @staticmethod
    def _serialize_order(
        order: PaperOrder, ticker: str, cash: Decimal | None, replayed: bool = False
    ) -> dict[str, Any]:
        return {
            "order_id": order.id,
            "ticker": ticker,
            "side": order.side,
            "status": order.status,
            "quantity": order.quantity,
            "execution_price": order.execution_price,
            "stop_loss": order.stop_loss,
            "take_profit": order.take_profit,
            "realized_pnl": order.realized_pnl,
            "cash_after": cash,
            "idempotency_key": order.idempotency_key,
            "message": order.rejection_reason or "Paper order filled at the reference price.",
            "replayed": replayed,
        }
