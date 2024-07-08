"""Exchange interface"""

import abc
import asyncio

from core.types import Symbol


class Exchange:
    @abc.abstractmethod
    async def subscribe_ticker(self, symbol: Symbol, **_) -> asyncio.Queue:
        pass
