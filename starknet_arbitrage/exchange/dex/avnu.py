"""AVNU exchange interface."""

import asyncio
from decimal import Decimal
import decimal
import logging
import typing

from starknet_py.net.account.account import Account
import aiohttp
import requests

from ...core.types import Order, Symbol, Ticker, Token, Wallet
from ..base import Exchange

ETH = Token(
    "ETH", "0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7", 18
)


URLS = {
    "base": "https://starknet.api.avnu.fi",
    "quotes": "swap/v2/quotes",
    "prices": "swap/v2/prices",
    "sources": "swap/v2/sources",
    "build": "swap/v2/build",
}

logger = logging.getLogger("bot")


class AVNU(Exchange):
    """AVNU exchange."""

    def __init__(self, account: Account, balance: Symbol) -> None:
        self._account = account
        # Fetch available dexes
        response = requests.get(f"{URLS['base']}/{URLS['sources']}")
        available_dexes = [
            dex["name"] for dex in response.json() if dex["type"] == "DEX"
        ]
        available_dexes.append("custom")

        self._last_prices = {dex: Decimal("0") for dex in available_dexes}
        self._wallet_queue = asyncio.Queue()

        asyncio.create_task(self._fetch_balance(balance))

    def __str__(self) -> str:
        return f"{type(self).__name__}"

    async def _handle_prices(
        self,
        queue: asyncio.Queue,
        symbol: Symbol,
        keep_best: bool,
        amount: decimal.Decimal,
    ):
        url = f"{URLS['base']}/{URLS['prices']}"
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

    async def _handle_quotes(
        self,
        queue: asyncio.Queue,
        symbol: Symbol,
        amount: decimal.Decimal,
    ):
        url = f"{URLS['base']}/{URLS['quotes']}"
        params_sell = {
            "sellAmount": hex(amount * 10 ** int(symbol.base.decimals)),
            "sellTokenAddress": symbol.base.address,
            "buyTokenAddress": symbol.quote.address,
        }
        params_buy = {
            "sellAmount": hex(amount * 10 ** int(symbol.base.decimals)),
            "sellTokenAddress": symbol.base.address,
            "buyTokenAddress": symbol.quote.address,
        }

        async with aiohttp.ClientSession() as session:
            while True:
                logger.debug(f"Fetching quotes")
                # We need to make two requests because a call to `/quotes` also
                # sets the swap order. Therefore, if we want to buy `base` from
                # `quote` we need the opposite ordeer (and a new `quoteId`)
                resp_sell, resp_buy = await asyncio.gather(
                    session.get(url, params=params_sell),
                    session.get(url, params=params_buy),
                )
                entries_sell, entries_buy = await asyncio.gather(
                    resp_sell.json(), resp_buy.json()
                )

                # `entries_sell` is a list with one element
                entry = entries_sell[0]

                quote_amount = decimal.Decimal(int(entry["buyAmount"], 16))
                quote_amount = quote_amount / (10**symbol.quote.decimals)
                price = quote_amount / amount

                if self._last_prices["custom"] != price:
                    self._last_prices["custom"] = price
                    entry["lastPrice"] = price

                    entry["sellId"] = entry["quoteId"]
                    entry["buyId"] = entries_buy[0]["quoteId"]
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
        self, symbol: Symbol, amount: decimal.Decimal, **_
    ) -> asyncio.Queue:
        queue = asyncio.Queue()
        asyncio.create_task(self._handle_quotes(queue, symbol, amount))

        return queue

    async def subscribe_prices(
        self, symbol: Symbol, amount: decimal.Decimal, keep_best: bool = True
    ) -> asyncio.Queue:
        queue = asyncio.Queue()
        asyncio.create_task(self._handle_prices(queue, symbol, keep_best, amount))

        return queue

    async def buy_market_order(
        self, symbol: Symbol, amount: Decimal, ticker: Ticker, slippage: Decimal = 0.001
    ) -> Order:
        """Insert a buy market order."""
        url = f"{URLS['base']}/{URLS['build']}"

        payload = {
            "slippage": slippage,
            "takerAddress": hex(self._account.address),
            "quoteId": ticker.raw["quoteId"],
            "includeApprove": True,
        }

        # FIXME: Share session with `handle_prices_quotes`
        async with aiohttp.ClientSession() as session:
            response = await session.post(url, json=payload)
            calls = await response.json()
            transaction_hash = await self._account.execute_v3(calls)

            # Refresh wallet balances
            asyncio.create_task(self._fetch_balance(symbol))

            # NOTE: Transaction does not return swapped amounts. Simulate them
            return Order(
                {"transaction_hash": transaction_hash}, symbol, amount, 0, "buy"
            )

    async def sell_market_order(
        self, symbol: Symbol, amount: Decimal, ticker: Ticker, slippage: Decimal = 0.001
    ) -> Order:
        """Insert a sell market order."""
        url = f"{URLS['base']}/{URLS['build']}"
        # NOTE: `slippage` is hardcoded to 0.1%
        payload = {
            "slippage": slippage,
            "takerAddress": self._account.address,
            "quoteId": ticker.raw["quoteId"],
            "includeApprove": True,
        }

        # FIXME: Share session with `handle_prices_quotes`
        async with aiohttp.ClientSession() as session:
            response = await session.post(url, json=payload)
            calls = await response.json()
            transaction_hash = await self._account.execute_v3(calls)

            # Refresh wallet balances
            asyncio.create_task(self._fetch_balance(symbol))

            # NOTE: Transaction does not return swapped amounts. Simulate them
            return Order(
                {"transaction_hash": transaction_hash}, symbol, amount, 0, "sell"
            )
