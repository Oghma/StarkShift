"""Bot to monitor exchange spreads."""

import asyncio
import datetime
import decimal
import logging


import aiosqlite


from exchange.base import Exchange
from core.types import Symbol, Ticker

logger = logging.getLogger("bot")


class SpreadMonitor:

    def __init__(self, exchanges: list[Exchange], symbol: Symbol, config):
        self._exchanges = exchanges
        self._symbol = symbol
        self._config = config
        self._queue: asyncio.Queue[Ticker] = asyncio.Queue()

    async def _merge_queues(self, queue: asyncio.Queue):
        while True:
            val = await queue.get()
            await self._queue.put(val)

    async def _initialize(self):
        for exchange in self._exchanges:
            queue = await exchange.subscribe_ticker(
                self._symbol, amount=self._config.amount, keep_best=False
            )
            asyncio.create_task(self._merge_queues(queue))

    async def run(self):
        await self._initialize()

        db = await aiosqlite.connect("db.sqlite")

        last_prices = {}

        while True:
            msg = await self._queue.get()

            if "sourceName" in msg.raw:
                ex_name = msg.raw["sourceName"]
                last_prices[ex_name] = {
                    "last_price": msg.raw["lastPrice"],
                    "bid": msg.bid,
                    "ask": msg.ask,
                }
            else:
                ex_name = msg.raw["info"]["sourceName"]
                last_prices[ex_name] = {
                    "last_price": decimal.Decimal(msg.raw["info"]["c"]),
                    "bid": msg.bid,
                    "ask": msg.ask,
                }

            logger.debug(
                "updated prices: %s, last_price: %d, bid: %d ask: %d",
                ex_name,
                last_prices[ex_name]["last_price"],
                last_prices[ex_name]["bid"],
                last_prices[ex_name]["ask"],
            )

            other_exchanges = set(last_prices.keys()) - set([ex_name])
            data = []

            for other_ex in other_exchanges:
                now = datetime.datetime.now()
                ex1_entry = last_prices[ex_name]
                ex2_entry = last_prices[other_ex]

                spread_prices = abs(ex1_entry["last_price"] - ex2_entry["last_price"])
                spread_perc = spread_prices / ex1_entry["last_price"]

                spread_ex1 = ex1_entry["ask"] - ex2_entry["bid"]
                spread_ex1_perc = spread_ex1 / ex1_entry["ask"]

                spread_ex2 = ex2_entry["ask"] - ex1_entry["bid"]
                spread_ex2_perc = spread_ex2 / ex2_entry["ask"]

                logger.info(
                    "New spreads %s-%s spread last prices %.4f %.4f first %.4f %.4f second %.4f %.4f",
                    ex_name,
                    other_ex,
                    spread_prices,
                    spread_perc,
                    spread_ex1,
                    spread_ex1_perc,
                    spread_ex2,
                    spread_ex2_perc,
                )

                data.append(
                    [
                        now,
                        ex_name,
                        other_ex,
                        str(spread_prices),
                        str(spread_perc),
                        str(spread_ex1),
                        str(spread_ex1_perc),
                        str(spread_ex2),
                        str(spread_ex2_perc),
                        str(ex1_entry["last_price"]),
                        str(ex1_entry["bid"]),
                        str(ex1_entry["ask"]),
                        str(ex2_entry["last_price"]),
                        str(ex2_entry["bid"]),
                        str(ex2_entry["ask"]),
                    ]
                )

            await db.executemany(
                "INSERT INTO spreads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                data,
            )
            await db.commit()
