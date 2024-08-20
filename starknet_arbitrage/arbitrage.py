"""CEX-DEX arbitrage bot."""

import asyncio
from decimal import Decimal
import logging
from typing import Any

from .exchange.base import Exchange
from .core.types import Order, Symbol, Ticker, Wallet
from .strategies.spread import SpreadStrategy
from .strategies.amounts import AmountStrategy

logger = logging.getLogger("bot")


class Arbitrage:
    def __init__(
        self,
        exchanges: list[Exchange],
        symbol: Symbol,
        spread_strategy: SpreadStrategy,
        amount_strategy: AmountStrategy,
        trade_amount: Decimal,
    ):
        self._exchanges = exchanges
        self._symbol = symbol
        self._trade_amount = trade_amount
        self._spread = spread_strategy
        self._amount_strategy = amount_strategy

        self._queue: asyncio.Queue[tuple[Any, Exchange]] = asyncio.Queue()
        self._waiting_orders = set()

    async def _merge_queues(self, queue: asyncio.Queue, ex: Exchange):
        while True:
            val = await queue.get()
            await self._queue.put((val, ex))

    async def _initialize(self):
        for exchange in self._exchanges:
            await exchange.subscribe_ticker(
                self._symbol, amount=int(self._trade_amount)
            )
            queue = exchange.receiver_queue()
            asyncio.create_task(self._merge_queues(queue, exchange))

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
                case Order():
                    logger.info(
                        f"{exchange} order executed. {msg.side}: {msg.amount} @ {msg.price}"
                    )
                    self._waiting_orders.discard(exchange)
                case Ticker():
                    # We want to buy at the lowest price
                    if msg.ask <= best_ask.ask:
                        best_ask = msg
                        exchange_ask = exchange

                    # We Want to sell at the highest price
                    if msg.bid >= best_bid.bid:
                        best_bid = msg
                        exchange_bid = exchange

                    # Same exchange, skip
                    if exchange_bid == exchange_ask:
                        continue

                    # Check if there are pending orders
                    if self._waiting_orders:
                        continue

                    (profitable, spread) = self._spread.profitable_trade(
                        best_ask, best_bid
                    )
                    logger.debug(
                        f"spread: {spread} best ask: {best_ask.ask} best bid: {best_bid.bid}"
                    )
                    if profitable and (
                        amount := self._amount_strategy.calculate_amount(
                            best_ask,
                            best_bid,
                            wallets[exchange_ask][self._symbol.base.name],
                            wallets[exchange_bid][self._symbol.quote.name],
                        )
                    ):
                        logger.info(f"spread: {spread}, try to catch the opportunity")
                        logger.debug(
                            f"{exchange_ask}: putting buy: {amount} @ {best_ask.ask}"
                        )
                        logger.debug(
                            f"{exchange_bid}: putting sell: {amount} @ {best_bid.bid}"
                        )

                        self._waiting_orders.add(exchange_ask)
                        self._waiting_orders.add(exchange_bid)

                        await asyncio.gather(
                            exchange_ask.buy_market_order(
                                self._symbol, amount, best_ask
                            ),
                            exchange_bid.sell_market_order(
                                self._symbol, amount, best_bid
                            ),
                        )
