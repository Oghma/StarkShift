from __future__ import annotations

import argparse
import asyncio
import logging
import os
from dataclasses import InitVar, dataclass, field
from decimal import Decimal
from typing import Any

import yaml
from rich.logging import RichHandler
from rich.traceback import install as traceback_install

from .arbitrage import Arbitrage
from .core.types import Symbol, Token
from .exchange.cex.binance import Binance
from .exchange.dex.avnu import AVNU
from .starknet import Starknet
from .strategies.amounts import SimpleAmountStrategy
from .strategies.spread import SimpleSpreadStrategy


# Install rich traceback handler for a better traceback experience
traceback_install(show_locals=False)


@dataclass
class Config:
    base: Token = field(init=False)
    quote: Token = field(init=False)
    symbol: Symbol = field(init=False)
    api_key: str
    secret_key: str
    node_url: str
    account_address: str
    signer_key: str
    spread_threshold: Decimal
    max_amount_trade: Decimal
    min_amount_trade: Decimal

    base_name: InitVar[str]
    base_decimals: InitVar[int]
    base_address: InitVar[str]
    quote_name: InitVar[str]
    quote_decimals: InitVar[int]
    quote_address: InitVar[str]

    def __post_init__(
        self,
        base_name: str,
        base_decimals: int,
        base_address: str,
        quote_name: str,
        quote_decimals: int,
        quote_address: str,
    ):
        self.base = Token(base_name.upper(), base_address, base_decimals)
        self.quote = Token(quote_name.upper(), quote_address, quote_decimals)
        self.symbol = Symbol(self.base, self.quote)

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> Config:
        for key in ["spread_threshold", "max_amount_trade", "min_amount_trade"]:
            config_dict[key] = Decimal(str(config_dict[key]))

        return cls(**config_dict)

    @classmethod
    def load_config(cls, config_path: str = "config.yaml") -> Config:
        with open(config_path, "r") as fpt:
            config_dict = yaml.safe_load(fpt)

        for key in config_dict:
            if env_value := os.getenv(key.upper()):
                config_dict[key] = env_value

        return cls.from_dict(config_dict)


def custom_exception_handler(loop, context):
    # First, handle with default handler
    loop.default_exception_handler(context)

    # Terminates for any exception
    if context.get("exception"):
        loop.stop()


async def main(config_file: str):
    # Bot settings
    logger = logging.getLogger("bot")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(RichHandler())
    # Load config
    config = Config.load_config(config_file)

    # Add a custom exception handler to shutdown when a coroutine fails
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(custom_exception_handler)

    # Exchange initialisation
    logger.debug("Connecting to starknet...")
    chain = Starknet(config.node_url)
    account = chain.get_account(config.account_address, config.signer_key)

    logger.debug("Connecting to AVNU...")
    avnu = AVNU(account, config.symbol)

    logger.debug("Connecting to binance...")
    binance = Binance(config.api_key, config.secret_key)

    # Build spread strategy
    spread_strategy = SimpleSpreadStrategy(config.spread_threshold)

    # Build amount strategy
    amount_strategy = SimpleAmountStrategy(
        config.max_amount_trade, config.min_amount_trade
    )

    # Run bot
    logger.debug("All setup, running bot...")
    bot = Arbitrage(
        [binance, avnu],
        config.symbol,
        spread_strategy,
        amount_strategy,
        config.max_amount_trade,
    )
    await bot.run()


DEFAULT_CONFIG_LOCATION = "config/config.yml"

PARSER = argparse.ArgumentParser(
    prog="python -m starkshift",
    description="starkshift arbitrage bot.",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
PARSER.add_argument(
    "config",
    nargs="?",
    default=DEFAULT_CONFIG_LOCATION,
    help="path to the configuration file",
    metavar="CONFIG_PATH",
)
ARGS = PARSER.parse_args()

asyncio.run(main(ARGS.config))
