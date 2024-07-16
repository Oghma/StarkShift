"""Exchange interface"""

import abc
import asyncio
from decimal import Decimal
import typing

from ..core.types import Order, Symbol


class Exchange:
    @abc.abstractmethod
    async def subscribe_ticker(self, symbol: Symbol, **_) -> asyncio.Queue:
        """Subscribe to the ticker channel. Return the queue containing the messages"""

    @abc.abstractmethod
    async def subscribe_wallet(
        self, symbol: typing.Optional[Symbol] = None
    ) -> asyncio.Queue:
        """Subscribe to the wallet channel. Return the queue containing the messages"""

    @abc.abstractmethod
    async def buy_market_order(
        self, symbol: Symbol, amount: Decimal, *args, **kwargs
    ) -> Order:
        """Insert a buy market order."""

    @abc.abstractmethod
    async def sell_market_order(
        self, symbol: Symbol, amount: Decimal, *args, **kwargs
    ) -> Order:
        """Insert a sell market order."""
