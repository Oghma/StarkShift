"""Binance exchange interface."""

import asyncio
from decimal import Decimal

import ccxt.pro

from core.types import Symbol, Ticker
from ..base import Exchange


class Binance(Exchange):
    """Binance exchange."""

    def __init__(self, **_) -> None:
        self._exchange_handle = ccxt.pro.binance()
        self._ticker_queues = {}

    async def subscribe_ticker(self, symbol: Symbol, **_) -> asyncio.Queue:
        """Subscribe to the ticker."""
        exchange_symbol = f"{symbol.base.name}{symbol.quote.name}"
        queue = asyncio.Queue()
        self._ticker_queues[exchange_symbol] = queue

        asyncio.create_task(self._handle_ticker(exchange_symbol))
        return queue

    async def _handle_ticker(self, symbol: str):
        """Handle ticker messages and connection."""
        queue = self._ticker_queues[symbol]

        while True:
            msg = await self._exchange_handle.watch_ticker(symbol)
            msg["info"]["sourceName"] = "binance"

            ticker = Ticker(
                msg,
                Decimal(msg["info"]["b"]),
                Decimal(msg["info"]["B"]),
                Decimal(msg["info"]["a"]),
                Decimal(msg["info"]["A"]),
            )

            await queue.put(ticker)
