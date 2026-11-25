"""Execution boundary shared by simulated brokers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BrokerFill:
    quantity: Decimal
    price: Decimal
    fee: Decimal = Decimal("0")


class BrokerInterface(ABC):
    @abstractmethod
    def execute_market_order(
        self, *, side: str, quantity: Decimal, reference_price: Decimal
    ) -> BrokerFill:
        """Return a fill or raise an execution error."""
