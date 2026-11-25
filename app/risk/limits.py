"""Typed deterministic limits for the paper-trading account."""

from dataclasses import dataclass
from decimal import Decimal

from app.config import Settings


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade: Decimal
    max_position_exposure: Decimal
    max_portfolio_exposure: Decimal
    max_daily_loss: Decimal
    max_open_positions: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "RiskLimits":
        return cls(
            risk_per_trade=Decimal(str(settings.max_risk_per_trade_pct)),
            max_position_exposure=Decimal(str(settings.max_position_pct)),
            max_portfolio_exposure=Decimal(str(settings.max_portfolio_exposure_pct)),
            max_daily_loss=Decimal(str(settings.max_daily_loss_pct)),
            max_open_positions=settings.max_open_positions,
        )
