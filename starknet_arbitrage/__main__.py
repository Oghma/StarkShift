import asyncio
import logging
import os

from dotenv import dotenv_values
from rich.logging import RichHandler

from .arbitrage import Arbitrage
from .core.types import Symbol, Token
from .exchange.cex.binance import Binance
from .exchange.dex.avnu import AVNU
from .starknet import Starknet


class ValidationError(Exception):
    pass


class Config:

    REQUIRED_KEYS = {
        "BASE_ADDR",
        "BASE_DECIMALS",
        "BASE",
        "QUOTE_ADDR",
        "QUOTE_DECIMALS",
        "QUOTE",
        "SWAP_AMOUNT",
        "API_KEY",
        "SECRET_KEY",
    }

    def __init__(self, config: dict) -> None:
        for key in self.REQUIRED_KEYS:
            if key not in config:
                raise ValidationError(f"Missing `key`")

        self.base = Token(
            config["BASE"], config["BASE_ADDR"], int(config["BASE_DECIMALS"])
        )
        self.quote = Token(
            config["QUOTE"], config["QUOTE_ADDR"], int(config["QUOTE_DECIMALS"])
        )
        self.symbol = Symbol(self.base, self.quote)
        self.amount = int(config["SWAP_AMOUNT"])

        self.api_key = config["API_KEY"]
        self.secret_key = config["SECRET_KEY"]


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
