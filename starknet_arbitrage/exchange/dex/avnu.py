"""AVNU exchange interface."""

import asyncio
from decimal import Decimal
import decimal
import logging
import typing

from starknet_py.net.account.account import Account
from starknet_py.hash.selector import get_selector_from_name
from starknet_py.net.client_models import Call

import aiohttp

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
        self._receiver_queue = asyncio.Queue()

        asyncio.create_task(self._fetch_balance(balance))

    def __str__(self) -> str:
        return f"{type(self).__name__}"

    async def _handle_prices(
        self,
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
                logger.debug("Fetching prices")
                response = await session.get(url, params=params)
                entries = await response.json()

                if keep_best:
                    entries = [entries[0]]

                for entry in entries:
                    quote_amount = decimal.Decimal(int(entry["buyAmount"], 16))
                    quote_amount = quote_amount / (10**symbol.quote.decimals)
                    price = quote_amount / amount

                    ticker = Ticker(entry, price, amount, price, quote_amount)
                    await self._receiver_queue.put(ticker)

                await asyncio.sleep(1)

    async def _handle_quotes(
        self,
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
                logger.debug("Fetching quotes")
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

                entry["sellId"] = entry["quoteId"]
                entry["buyId"] = entries_buy[0]["quoteId"]
                ticker = Ticker(entry, price, amount, price, amount)

                await self._receiver_queue.put(ticker)
                await asyncio.sleep(1)

    async def _fetch_balance(self, symbol: typing.Optional[Symbol] = None):
        tokens = [ETH] if symbol is None else [symbol.base, symbol.quote]

        for token in tokens:
            logger.debug(f"Fetching {token.address} balance")
            amount = await self._account.get_balance(token.address)
            await self._receiver_queue.put(
                Wallet({"amount": amount}, token, Decimal(amount) / 10**token.decimals)
            )

    async def _wait_txn(
        self,
        transaction_hash: int,
        symbol: Symbol,
        amount: Decimal,
        ticker: Ticker,
        side: str,
    ):
        """Wait until transaction is confirmed. After create the order and update the balance."""
        await self._account.client.wait_for_tx(transaction_hash)

        order = Order(
            {"transaction_hash": transaction_hash},
            symbol,
            amount,
            # NOTE: `ask` and `bid` are the same
            ticker.ask,
            side,
        )
        await self._receiver_queue.put(order)

        asyncio.create_task(self._fetch_balance(symbol))

    async def subscribe_ticker(self, symbol: Symbol, amount: decimal.Decimal, **_):
        asyncio.create_task(self._handle_quotes(symbol, amount))

    async def subscribe_prices(
        self, symbol: Symbol, amount: decimal.Decimal, keep_best: bool = True
    ):
        asyncio.create_task(self._handle_prices(symbol, keep_best, amount))

    async def buy_market_order(
        self,
        symbol: Symbol,
        amount: Decimal,
        ticker: Ticker,
        slippage: Decimal = Decimal("0.01"),
    ):
        """Insert a buy market order."""
        url = f"{URLS['base']}/{URLS['build']}"

        payload = {
            "slippage": str(slippage),
            "takerAddress": hex(self._account.address),
            "quoteId": ticker.raw["quoteId"],
            "includeApprove": True,
        }

        # FIXME: Share session with `handle_prices_quotes`
        async with aiohttp.ClientSession() as session:
            response = await session.post(url, json=payload)
            resp_calls = await response.json()

            # `resp_calls` is a dict containing `chainId` and `calls` keys. A
            # call is a dict containing `contractAddress, entrypoint` and
            # `calldata`. Values are hexed or string (the selector)
            calls = [
                Call(
                    int(call["contractAddress"], 16),
                    get_selector_from_name(call["entrypoint"]),
                    [int(call_value, 16) for call_value in call["calldata"]],
                )
                for call in resp_calls["calls"]
            ]

            logger.info("sending order")
            transaction_hash = await self._account.execute_v3(calls, auto_estimate=True)
            await self._wait_txn(
                transaction_hash.transaction_hash, symbol, amount, ticker, "buy"
            )

    def receiver_queue(self) -> asyncio.Queue:
        """Return the queue containing the messages from the Exchange."""
        return self._receiver_queue

    async def sell_market_order(
        self,
        symbol: Symbol,
        amount: Decimal,
        ticker: Ticker,
        slippage: Decimal = Decimal("0.01"),
    ):
        """Insert a sell market order."""
        url = f"{URLS['base']}/{URLS['build']}"
        # NOTE: `slippage` is hardcoded to 0.1%
        payload = {
            "slippage": str(slippage),
            "takerAddress": hex(self._account.address),
            "quoteId": ticker.raw["quoteId"],
            "includeApprove": True,
        }

        # FIXME: Share session with `handle_prices_quotes`
        async with aiohttp.ClientSession() as session:
            response = await session.post(url, json=payload)
            resp_calls = await response.json()

            # `resp_calls` is a dict containing `chainId` and `calls` keys. A
            # call is a dict containing `contractAddress, entrypoint` and
            # `calldata`. Values are hexed or string (the selector)
            calls = [
                Call(
                    int(call["contractAddress"], 16),
                    get_selector_from_name(call["entrypoint"]),
                    [int(call_value, 16) for call_value in call["calldata"]],
                )
                for call in resp_calls["calls"]
            ]

            logger.info("sending order")
            transaction_hash = await self._account.execute_v3(calls, auto_estimate=True)
            await self._wait_txn(
                transaction_hash.transaction_hash, symbol, amount, ticker, "sell"
            )
