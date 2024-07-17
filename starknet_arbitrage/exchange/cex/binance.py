"""Binance exchange interface."""

import asyncio
from decimal import Decimal
import typing

import ccxt.pro

from ...core.types import Symbol, Ticker, Token, Wallet, Order
from ..base import Exchange


class Binance(Exchange):
    """Binance exchange."""

    def __init__(self, api_key: str, secret_key: str) -> None:
        self._exchange_handle = ccxt.pro.binance(
            {"apiKey": api_key, "secret": secret_key}
        )
        self._ticker_queues = {}
        self._wallet_queue = asyncio.Queue()

    def __str__(self) -> str:
        return f"{type(self).__name__}"

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

    async def _fetch_wallet(self, symbol: typing.Optional[Symbol] = None):
        """Fetch balances.

        Only balances of the tokens in `Symbol` are sent to the queue. If None,
        send all tokens.

        """
        msg = await self._exchange_handle.fetch_balance()
        if symbol is not None:
            tokens = [symbol.base, symbol.quote]
        else:
            tokens = [Token(tok["asset"], "", 18) for tok in msg["info"]["balances"]]

        for token in tokens:
            balance = msg[token.name]
            await self._wallet_queue.put(
                Wallet(balance, token, Decimal(str(balance["free"])))
            )

    async def subscribe_ticker(self, symbol: Symbol, **_) -> asyncio.Queue:
        """Subscribe to the ticker."""
        exchange_symbol = f"{symbol.base.name}{symbol.quote.name}"
        queue = asyncio.Queue()
        self._ticker_queues[exchange_symbol] = queue

        asyncio.create_task(self._handle_ticker(exchange_symbol))
        return queue

    async def subscribe_wallet(
        self, symbol: typing.Optional[Symbol] = None
    ) -> asyncio.Queue:
        asyncio.create_task(self._fetch_wallet(symbol))
        return self._wallet_queue

    async def buy_market_order(
        self, symbol: Symbol, amount: Decimal, *_, **__
    ) -> Order:
        """Insert a new buy market order."""
        exchange_symbol = f"{symbol.base.name}{symbol.quote.name}"

        order = await self._exchange_handle.create_order_ws(
            exchange_symbol, "market", "buy", float(amount), params={"test": True}
        )

        return Order(
            order, symbol, Decimal(str(order.price)), Decimal(str(order.amount)), "buy"
        )

    async def sell_market_order(
        self, symbol: Symbol, amount: Decimal, *_, **__
    ) -> Order:
        """Insert a new sell market order."""
        exchange_symbol = f"{symbol.base.name}{symbol.quote.name}"

        order = await self._exchange_handle.create_order_ws(
            exchange_symbol, "market", "sell", float(amount), params={"test": True}
        )

        return Order(
            order, symbol, Decimal(str(order.price)), Decimal(str(order.amount)), "sell"
        )
