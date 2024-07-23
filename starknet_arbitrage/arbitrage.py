"""CEX-DEX arbitrage bot."""

import asyncio
import dataclasses
from decimal import Decimal
import logging
from typing import Any

from attr import dataclass

from .exchange.base import Exchange
from .core.types import Symbol, Ticker, Wallet

logger = logging.getLogger("bot")


class Arbitrage:
    def __init__(
        self,
        exchanges: list[Exchange],
        symbol: Symbol,
        spread_threshold: Decimal,
        trade_amount: Decimal,
        min_trade_amount: Decimal,
    ):
        self._exchanges = exchanges
        self._symbol = symbol
        self._threshold = spread_threshold
        self._queue: asyncio.Queue[tuple[Any, Exchange]] = asyncio.Queue()
        self._trade_amount = trade_amount
        self._min_trade_amount = min_trade_amount

    async def _merge_queues(self, queue: asyncio.Queue, ex: Exchange):
        while True:
            val = await queue.get()
            await self._queue.put((val, ex))

    async def _initialize(self):
        for exchange in self._exchanges:
            queue = await exchange.subscribe_ticker(
                self._symbol, amount=int(self._trade_amount)
            )
            asyncio.create_task(self._merge_queues(queue, exchange))

    def _calculate_spread(self, ask: Decimal, bid: Decimal) -> Decimal:
        numerator = bid - ask
        return numerator / bid

    def _calculate_amount(
        self,
        ask: Ticker,
        bid: Ticker,
        wallet_ask: Decimal,
        wallet_bid: Decimal,
    ) -> Decimal:
        """Return the amount we can trade."""
        amount = min(self._trade_amount, ask.ask_amount, bid.bid_amount)
        # Check wallets have enough balance
        # NOTE: `wallet_ask` is the quote token balance. Convert in base
        amount = min(amount, wallet_bid, wallet_ask * ask.ask)

        return amount

    async def run(self):
        # Subscribe to the tickers and merge the queues
        await self._initialize()

        best_bid = Ticker({}, Decimal("-INFINITY"), Decimal(0), Decimal(0), Decimal(0))
        best_ask = Ticker({}, Decimal(0), Decimal(0), Decimal("INFINITY"), Decimal(0))
        exchange_ask = exchange_bid = self._exchanges[0]

        wallets = {
            exchange: {
                self._symbol.base.name: Wallet.empty(self._symbol.base),
                self._symbol.quote.name: Wallet.empty(self._symbol.quote),
            }
            for exchange in self._exchanges
        }

        while True:
            msg, exchange = await self._queue.get()

            match msg:
                case Wallet():
                    wallets[exchange][msg.token.name] = msg
                case Ticker():
                    # We want to buy at the lowest price
                    if msg.ask <= best_ask.ask:
                        best_ask = msg
                        exchange_ask = exchange

                    # We want to sell at the highest price
                    if msg.bid >= best_bid.bid:
                        best_bid = msg
                        exchange_bid = exchange

                    # Same exchange, skip
                    if exchange_bid == exchange_ask:
                        continue

                    spread = self._calculate_spread(
                        best_ask.ask,
                        best_bid.bid,
                    )
                    ba = dataclasses.replace(best_ask)
                    ba.raw = exchange_ask
                    bb = dataclasses.replace(best_bid)
                    bb.raw = exchange_bid

                    logger.debug(f"spread {spread} {ba.ask} {bb.bid} \n{ba}, {bb}")
                    if spread >= self._threshold:
                        logger.info(f"{spread} above the threshdold")
                        amount = self._calculate_amount(
                            best_ask,
                            best_bid,
                            wallets[exchange_ask][self._symbol.base.name].amount,
                            wallets[exchange_bid][self._symbol.quote.name].amount,
                        )

                        if amount <= self._min_trade_amount:
                            continue

                        logger.debug(
                            f"{exchange_ask}: buy: {amount} price: {best_ask.ask}"
                        )
                        logger.debug(
                            f"{exchange_bid}: sell: {amount} price: {best_bid.bid}"
                        )

                        order_ask, order_bid = await asyncio.gather(
                            exchange_ask.buy_market_order(
                                self._symbol, amount, best_ask
                            ),
                            exchange_bid.sell_market_order(
                                self._symbol, amount, best_bid
                            ),
                        )

                        logger.info(
                            f"{exchange_ask}: bought: {order_ask.amount} price: {order_ask.price}"
                        )
                        logger.info(
                            f"{exchange_bid}: sold: {order_bid.amount} price: {order_bid.price}"
                        )
