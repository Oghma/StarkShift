"""Exchange interface"""

import abc
import asyncio
from decimal import Decimal

from ..core.types import Symbol


class Exchange:
    @abc.abstractmethod
    async def subscribe_ticker(self, symbol: Symbol, **_):
        """Subscribe to the ticker channel."""

    @abc.abstractmethod
    async def buy_market_order(self, symbol: Symbol, amount: Decimal, *args, **kwargs):
        """Insert a buy market order."""

    @abc.abstractmethod
    def receiver_queue(self) -> asyncio.Queue:
        """Return the queue containing the messages from the Exchange."""

    @abc.abstractmethod
    async def sell_market_order(self, symbol: Symbol, amount: Decimal, *args, **kwargs):
        """Insert a sell market order."""
