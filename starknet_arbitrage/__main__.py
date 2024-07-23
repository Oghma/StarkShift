import asyncio
import logging
import os

from decimal import Decimal

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
        "API_KEY",
        "SECRET_KEY",
        "SIGNER_KEY",
        "NODE_URL",
        "SPREAD_THRESHOLD",
        "MAX_AMOUNT_TRADE",
    }

    def __init__(self, config: dict) -> None:
        for key in self.REQUIRED_KEYS:
            if key not in config:
                raise ValidationError(f"Missing `{key}`")

        self.base = Token(
            config["BASE"], config["BASE_ADDR"], int(config["BASE_DECIMALS"])
        )
        self.quote = Token(
            config["QUOTE"], config["QUOTE_ADDR"], int(config["QUOTE_DECIMALS"])
        )
        self.symbol = Symbol(self.base, self.quote)

        self.api_key = config["API_KEY"]
        self.secret_key = config["SECRET_KEY"]

        self.node_url = config["NODE_URL"]
        self.account_address = config["ACCOUNT_ADDRESS"]
        self.signer_key = config["SIGNER_KEY"]

        self.spread_threshold = Decimal(config["SPREAD_THRESHOLD"])
        self.max_amount_trade = Decimal(config["MAX_AMOUNT_TRADE"])
        self.min_amount_trade = Decimal(config["MIN_AMOUNT_TRADE"])


async def main():
    # Bot settings
    logger = logging.getLogger("bot")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(RichHandler())
    # Load config
    config = {**dotenv_values(".env"), **os.environ}
    config = Config(config)

    # Exchange initialisation
    logger.debug("Connecting to starknet...")
    chain = Starknet(config.node_url)
    account = chain.get_account(config.account_address, config.signer_key)
    logger.debug("Connecting to AVNU...")
    avnu = AVNU(account, config.symbol)

    logger.debug("Connecting to binance...")
    binance = Binance(config.api_key, config.secret_key)

    # Run bot
    logger.debug("All setup, running bot...")
    bot = Arbitrage(
        [binance, avnu],
        config.symbol,
        config.spread_threshold,
        config.max_amount_trade,
        config.min_amount_trade,
    )
    await bot.run()


asyncio.run(main())
