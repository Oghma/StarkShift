"""Exchange interface"""

import abc
import asyncio
import typing

from ..core.types import Symbol


class Exchange:
    @abc.abstractmethod
    async def subscribe_ticker(self, symbol: Symbol, **_) -> asyncio.Queue:
        pass

    @abc.abstractmethod
    async def subscribe_wallet(
        self, symbol: typing.Optional[Symbol] = None
    ) -> asyncio.Queue:
        pass
