"""Pre-trade checks for the paper broker."""

from decimal import Decimal

from app.risk.limits import RiskLimits
from app.risk.position_sizing import PositionSizer


class RiskRejected(ValueError):
    """A deterministic risk rule rejected the proposed paper order."""


class RiskValidator:
    def __init__(self, limits: RiskLimits, sizer: PositionSizer | None = None) -> None:
        self.limits = limits
        self.sizer = sizer or PositionSizer()

    def validate_buy(
        self,
        *,
        equity: Decimal,
        cash: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
        position_count: int,
        already_holding: bool,
        position_value: Decimal,
        total_exposure: Decimal,
        realized_pnl_today: Decimal,
    ) -> Decimal:
        if stop_loss is None:
            raise RiskRejected("A validated stop loss is required before a BUY")
        if take_profit is not None and take_profit <= entry_price:
            raise RiskRejected("A BUY take-profit must be above the entry price")
        if realized_pnl_today <= -(equity * self.limits.max_daily_loss):
            raise RiskRejected("The portfolio has reached its configured daily loss limit")
        if not already_holding and position_count >= self.limits.max_open_positions:
            raise RiskRejected("The maximum number of open positions has been reached")
        try:
            quantity = self.sizer.quantity(
                equity=equity,
                available_cash=cash,
                entry_price=entry_price,
                stop_loss=stop_loss,
                current_position_value=position_value,
                total_exposure=total_exposure,
                risk_per_trade=self.limits.risk_per_trade,
                max_position_exposure=self.limits.max_position_exposure,
                max_portfolio_exposure=self.limits.max_portfolio_exposure,
            )
        except ValueError as exc:
            raise RiskRejected(str(exc)) from exc
        if quantity <= 0:
            raise RiskRejected("Risk limits leave no room for a whole-share position")
        return quantity
