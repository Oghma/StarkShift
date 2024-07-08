import asyncio
import logging
import os

from dotenv import dotenv_values
from rich.logging import RichHandler

from arbitrage import Arbitrage
from price_monitor import SpreadMonitor
from core.types import Symbol, Token
from exchange.cex.binance import Binance
from exchange.dex.avnu import AVNU


class ValidationError(Exception):
    pass


class Config:

    def __init__(self, config: dict) -> None:
        if "BASE" not in config:
            raise ValidationError("Missing `BASE`")
        if "BASE_ADDR" not in config:
            raise ValidationError("Missing `BASE_ADDR`")
        if "BASE_DECIMALS" not in config:
            raise ValidationError("Missing `BASE_DECIMALS`")
        self.base = Token(
            config["BASE"], config["BASE_ADDR"], int(config["BASE_DECIMALS"])
        )

        if "QUOTE" not in config:
            raise ValidationError("Missing `QUOTE`")
        if "QUOTE_ADDR" not in config:
            raise ValidationError("Missing `QUOTE_ADDR`")
        if "QUOTE_DECIMALS" not in config:
            raise ValidationError("Missing `QUOTE_DECIMALS`")
        self.quote = Token(
            config["QUOTE"], config["QUOTE_ADDR"], int(config["QUOTE_DECIMALS"])
        )
        self.symbol = Symbol(self.base, self.quote)

        if "SWAP_AMOUNT" not in config:
            raise ValidationError("Missing `SWAP_AMOUNT`")
        self.amount = int(config["SWAP_AMOUNT"])


async def main():
    logger = logging.getLogger("bot")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(RichHandler())

    config = {**dotenv_values(".env"), **os.environ}
    config = Config(config)

    binance = Binance()
    avnu = AVNU()

    monitor = SpreadMonitor([binance, avnu], config.symbol, config)
    await monitor.run()


asyncio.run(main())
