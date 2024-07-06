"""Binance exhange interface."""

import asyncio
from decimal import Decimal

from ccxt import Exchange
import ccxt.pro

from core.types import Symbol, Ticker


class Binance(Exchange):
    """Binance exchange representation."""

    def __init__(self) -> None:
        self._exchange_handle = ccxt.pro.binance()
        self._ticker_queues = {}

    async def subscribe_ticker(self, symbol: Symbol) -> asyncio.Queue:
        """Subscribe to the ticker."""
        exchange_symbol = f"{symbol.base}{symbol.quote}"
        queue = asyncio.Queue()
        self._ticker_queues[exchange_symbol] = queue

        asyncio.create_task(self._handle_ticker(exchange_symbol))
        return queue

    async def _handle_ticker(self, symbol: str):
        """Handle ticker messages and connection."""
        queue = self._ticker_queues[symbol]

        while True:
            msg = await self._exchange_handle.watch_ticker(symbol)
            ticker = Ticker(
                msg,
                Decimal(msg["info"]["b"]),
                Decimal(msg["info"]["B"]),
                Decimal(msg["info"]["a"]),
                Decimal(msg["info"]["A"]),
            )

            await queue.put(ticker)
