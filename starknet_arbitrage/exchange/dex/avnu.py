"""AVNU exchange interface."""

import asyncio
from decimal import Decimal
import decimal

from ccxt.async_support.base.exchange import aiohttp
import requests

from core.types import Symbol, Ticker
from ..base import Exchange


URLS = {
    "base": "https://starknet.api.avnu.fi",
    "ticker": "swap/v2/prices",
    "sources": "/swap/v2/sources",
}


class AVNU(Exchange):
    """AVNU exchange."""

    def __init__(self) -> None:
        # Fetch available dexes
        response = requests.get(f"{URLS['base']}/{URLS['sources']}")
        self._available_dexes = [dex["name"] for dex in response.json()]
        self._last_prices = {dex: Decimal("0") for dex in self._available_dexes}

    async def _handle_ticker(
        self,
        queue: asyncio.Queue,
        symbol: Symbol,
        keep_best: bool,
        amount: decimal.Decimal,
    ):
        url = f"{URLS['base']}/{URLS['ticker']}"
        params = {
            "sellAmount": hex(amount * 10 ** int(symbol.base.decimals)),
            "sellTokenAddress": symbol.base.address,
            "buyTokenAddress": symbol.quote.address,
        }

        async with aiohttp.ClientSession() as session:

            while True:
                response = await session.get(url, params=params)
                entries = await response.json()

                if keep_best:
                    entries = [entries[0]]

                for entry in entries:
                    quote_amount = decimal.Decimal(int(entry["buyAmount"], 16))
                    quote_amount = quote_amount / (10**symbol.quote.decimals)
                    price = quote_amount / amount

                    if self._last_prices[entry["sourceName"]] != price:
                        self._last_prices[entry["sourceName"]] = price
                        entry["lastPrice"] = price
                        ticker = Ticker(entry, price, amount, price, quote_amount)

                        await queue.put(ticker)

                await asyncio.sleep(1)

    async def subscribe_ticker(
        self, symbol: Symbol, amount: decimal.Decimal, keep_best: bool = True, **_
    ) -> asyncio.Queue:
        queue = asyncio.Queue()
        asyncio.create_task(self._handle_ticker(queue, symbol, keep_best, amount))

        return queue
