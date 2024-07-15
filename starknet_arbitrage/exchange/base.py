"""Exchange interface"""

import abc
import asyncio
import typing

from ..core.types import Symbol


class Exchange:
    @abc.abstractmethod
    async def subscribe_ticker(self, symbol: Symbol, **_) -> asyncio.Queue:
        """Subscribe to the ticker channel. Return the queue containing the messages"""

    @abc.abstractmethod
    async def subscribe_wallet(
        self, symbol: typing.Optional[Symbol] = None
    ) -> asyncio.Queue:
        """Subscribe to the wallet channel. Return the queue containing the messages"""
