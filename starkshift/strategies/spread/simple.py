"""Define `SimpleSpreadStrategy`."""

from decimal import Decimal
from typing import Union

from ...core.types import Ticker
from .base import SpreadStrategy


class SimpleSpreadStrategy(SpreadStrategy):
    """Simple spread strategy calculation.

    Spread is calculated as: (bid - ask) / bid

    """

    def __init__(self, threshold: Union[Decimal, float]) -> None:
        self._threshold = Decimal(str(threshold))

    def spread(self, ask: Ticker, bid: Ticker) -> Decimal:
        """Return the spread between ask and bid."""
        numerator = bid.bid - ask.ask
        return numerator / bid.bid

    def profitable_trade(self, ask: Ticker, bid: Ticker) -> tuple[bool, Decimal]:
        """Return if there is a profitable trade and the spread between ask and bid."""
        spread = self.spread(ask, bid)
        return (spread >= self._threshold, spread)
