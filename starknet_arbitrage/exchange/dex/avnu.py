"""AVNU exchange interface."""

import asyncio
from decimal import Decimal
import decimal
import logging
import typing

from starknet_py.net.account.account import Account
import aiohttp
import requests

from ...core.types import Symbol, Ticker, Token, Wallet
from ..base import Exchange

ETH = Token(
    "ETH", "0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7", 18
)


URLS = {
    "base": "https://starknet.api.avnu.fi",
    "quotes": "swap/v2/quotes",
    "prices": "swap/v2/prices",
    "sources": "/swap/v2/sources",
}

logger = logging.getLogger("bot")


class AVNU(Exchange):
    """AVNU exchange."""

    def __init__(self, account: Account) -> None:
        self._account = account
        # Fetch available dexes
        response = requests.get(f"{URLS['base']}/{URLS['sources']}")
        self._available_dexes = [dex["name"] for dex in response.json()]
        self._last_prices = {dex: Decimal("0") for dex in self._available_dexes}
        self._wallet_queue = asyncio.Queue()

    def __str__(self) -> str:
        return f"{type(self).__name__}"

    async def _handle_prices_quotes(
        self,
        endpoint: str,
        queue: asyncio.Queue,
        symbol: Symbol,
        keep_best: bool,
        amount: decimal.Decimal,
    ):
        url = f"{URLS['base']}/{URLS[endpoint]}"
        params = {
            "sellAmount": hex(amount * 10 ** int(symbol.base.decimals)),
            "sellTokenAddress": symbol.base.address,
            "buyTokenAddress": symbol.quote.address,
        }

        async with aiohttp.ClientSession() as session:

            while True:
                logger.debug(f"Fetching prices")
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

    async def _fetch_balance(self, symbol: typing.Optional[Symbol] = None):
        tokens = [ETH] if symbol is None else [symbol.base, symbol.quote]

        for token in tokens:
            logger.debug(f"Fetching {token.address} balance")
            amount = await self._account.get_balance(token.address)
            await self._wallet_queue.put(
                Wallet({"amount": amount}, ETH, Decimal(amount) / 10**18)
            )

    async def subscribe_ticker(
        self, symbol: Symbol, amount: decimal.Decimal, keep_best: bool = True, **_
    ) -> asyncio.Queue:
        queue = asyncio.Queue()
        asyncio.create_task(
            self._handle_prices_quotes("quotes", queue, symbol, keep_best, amount)
        )

        return queue

    async def subscribe_prices(
        self, symbol: Symbol, amount: decimal.Decimal, keep_best: bool = True, **_
    ) -> asyncio.Queue:
        queue = asyncio.Queue()
        asyncio.create_task(
            self._handle_prices_quotes("prices", queue, symbol, keep_best, amount)
        )

        return queue

    async def subscribe_wallet(
        self, symbol: typing.Optional[Symbol] = None
    ) -> asyncio.Queue:
        asyncio.create_task(self._fetch_balance(symbol))
        return self._wallet_queue
