"""Define the `SpreadStrategy` interface."""

import abc
from decimal import Decimal

from ...core.types import Ticker


class SpreadStrategy(abc.ABC):
    @abc.abstractmethod
    def spread(self, ask: Ticker, bid: Ticker) -> Decimal:
        """Return the spread between ask and bid."""

    @abc.abstractmethod
    def profitable_trade(self, ask: Ticker, bid: Ticker) -> tuple[bool, Decimal]:
        """Return if there is a profitable trade and the spread between ask and bid."""
