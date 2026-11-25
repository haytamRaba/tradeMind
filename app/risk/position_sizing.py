"""Whole-share position sizing under per-trade and exposure limits."""

from decimal import Decimal, ROUND_FLOOR


class PositionSizer:
    def quantity(
        self,
        *,
        equity: Decimal,
        available_cash: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        current_position_value: Decimal,
        total_exposure: Decimal,
        risk_per_trade: Decimal,
        max_position_exposure: Decimal,
        max_portfolio_exposure: Decimal,
    ) -> Decimal:
        if entry_price <= 0:
            raise ValueError("Entry price must be positive")
        if stop_loss <= 0 or stop_loss >= entry_price:
            raise ValueError("A BUY stop loss must be positive and below the entry price")
        if equity <= 0 or available_cash <= 0:
            raise ValueError("Portfolio equity and available cash must be positive")

        risk_per_share = entry_price - stop_loss
        risk_budget = equity * risk_per_trade
        position_capacity = max(Decimal("0"), equity * max_position_exposure - current_position_value)
        portfolio_capacity = max(Decimal("0"), equity * max_portfolio_exposure - total_exposure)
        maximum_value = min(
            risk_budget / risk_per_share * entry_price,
            position_capacity,
            portfolio_capacity,
            available_cash,
        )
        shares = (maximum_value / entry_price).to_integral_value(rounding=ROUND_FLOOR)
        return max(Decimal("0"), shares)
