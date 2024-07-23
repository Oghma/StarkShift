"""Binance exchange interface."""

import asyncio
from decimal import Decimal
import hashlib
import hmac
import logging
import time
import typing
import uuid

import aiohttp

from ...core.types import Order, Symbol, Ticker, Token, Wallet
from ..base import Exchange

BASE_URLS = {"http": "https://api.binance.com/", "wss": "wss://stream.binance.com:443/"}
ENDPOINTS = {"listenKey": "api/v3/userDataStream", "order": "api/v3/order "}

# Update the listen key every 30 minutes
LISTEN_KEY_UPDATE_EVERY = 1800

logger = logging.getLogger("bot")


class Binance(Exchange):
    """Binance exchange."""

    def __init__(self, api_key: str, secret_key: str) -> None:
        self._initialized = asyncio.Event()
        self._api_key = api_key
        self._secret = secret_key.encode("utf8")
        self._symbols = {}

        # TODO: Remove
        self._check_tokens = None

        asyncio.create_task(self._initialize(api_key))

        self._ticker_queues = {}
        self._wallet_queue = asyncio.Queue()

    def __str__(self) -> str:
        return f"{type(self).__name__}"

    async def _initialize(self, api_key: str):
        """Open and handle a connection to Binance."""
        headers = {"X-MBX-APIKEY": api_key}
        self._session = aiohttp.ClientSession(headers=headers)

        # Get the listenKey
        async with self._session.post(
            BASE_URLS["http"] + ENDPOINTS["listenKey"]
        ) as response:
            listen_key = await response.json()

        asyncio.create_task(self._keep_alive(listen_key))
        # Open the websocket
        self._ws_session = await self._session.ws_connect(
            BASE_URLS["wss"] + "ws/" + listen_key["listenKey"]
        )

        asyncio.create_task(self._handle_connection())
        self._initialized.set()

    async def _keep_alive(self, listen_key: dict[str, str]):
        """Keep alive the listen key."""
        while True:
            await asyncio.sleep(LISTEN_KEY_UPDATE_EVERY)

            async with self._session.put(
                BASE_URLS["http"] + ENDPOINTS["listenKey"], params=listen_key
            ) as resp:
                await resp.json()

    def _sign_message(self, payload: str) -> str:
        """Sign the payload for authenticated endponts."""
        msg = payload.encode("utf8")
        digest = hmac.new(self._secret, msg, hashlib.sha256)
        return digest.hexdigest()

    async def _handle_connection(self):
        """Handle websocket connection."""

        async for msg in self._ws_session:
            msg = msg.json()

            if msg["e"] == "24hrTicker":
                await self._handle_ticker(msg)
            elif msg["e"] == "outboundAccountPosition":
                await self._handle_wallet(msg)
            elif msg["e"] == "executionReport":
                await self._handle_order(msg)
            else:
                logger.debug("unknown message: ", msg)

    async def _handle_order(self, msg: dict):
        """Handle execution report messages."""
        order = Order(
            msg,
            self._symbols[msg["s"]],
            Decimal(msg["q"]),
            Decimal(msg["p"]),
            msg["S"].lower(),
        )
        queue = self._ticker_queues[(msg["s"])]
        await queue.put(order)

    async def _handle_ticker(self, msg: dict):
        """Handle ticker messages."""
        ticker = Ticker(
            msg,
            Decimal(msg["b"]),
            Decimal(msg["B"]),
            Decimal(msg["a"]),
            Decimal(msg["A"]),
        )
        queue = self._ticker_queues[(msg["s"])]
        await queue.put(ticker)

    async def _handle_wallet(self, msg: dict):
        """Handle message balances.

        Only balances of the tokens in `Symbol` are sent to the queue. If None,
        send all tokens.

        """
        tokens = (
            {}
            if self._check_tokens is None
            else {token.name: token for token in self._check_tokens}
        )

        for balance in msg["B"]:
            if not tokens or msg["a"] in tokens:
                await self._wallet_queue.put(
                    Wallet(balance, Token(balance["a"]), Decimal(balance["f"]))
                )

    async def subscribe_ticker(self, symbol: Symbol, **_) -> asyncio.Queue:
        """Subscribe to the ticker."""
        await self._initialized.wait()

        exchange_symbol = f"{symbol.base.name}{symbol.quote.name}".lower()
        queue = asyncio.Queue()
        self._ticker_queues[exchange_symbol] = queue

        payload = {
            "method": "SUBSCRIBE",
            "params": [f"{exchange_symbol}@ticker"],
            "id": str(uuid.uuid4()),
        }
        await self._ws_session.send_json(payload)
        logger.debug(f"Subscription sent for ticker {exchange_symbol}")
        return queue

    async def subscribe_wallet(
        self, symbol: typing.Optional[Symbol] = None
    ) -> asyncio.Queue:
        if symbol is not None:
            self._check_tokens = [symbol.base, symbol.quote]

        return self._wallet_queue

    async def buy_market_order(
        self, symbol: Symbol, amount: Decimal, *_args, **_kwargs
    ):
        """Insert a new buy market order."""
        exchange_symbol = f"{symbol.base.name}{symbol.quote.name}"
        params = {
            "symbol": exchange_symbol,
            "side": "BUY",
            "type": "MARKET",
            "quantity": str(amount),
            "apiKey": self._api_key,
            "timestamp": int(time.time() * 1000),  # timestamp in milliseconds
        }
        payload = "&".join(
            [f"{param}={value}" for param, value in sorted(params.items())]
        )
        signature = self._sign_message(payload)
        params["signature"] = signature

        async with self._session.post(
            BASE_URLS["http"] + ENDPOINTS["order"], params=params
        ) as response:
            await response.json()

    async def sell_market_order(
        self, symbol: Symbol, amount: Decimal, *_args, **_kwargs
    ):
        """Insert a new sell market order."""
        exchange_symbol = f"{symbol.base.name}{symbol.quote.name}"
        params = {
            "symbol": exchange_symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": str(amount),
            "apiKey": self._api_key,
            "timestamp": int(time.time() * 1000),  # timestamp in milliseconds
        }
        payload = "&".join(
            [f"{param}={value}" for param, value in sorted(params.items())]
        )
        signature = self._sign_message(payload)
        params["signature"] = signature

        async with self._session.post(
            BASE_URLS["http"] + ENDPOINTS["order"], params=params
        ) as response:
            await response.json()
