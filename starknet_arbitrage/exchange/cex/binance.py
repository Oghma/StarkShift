"""Binance exchange interface."""

import asyncio
from decimal import Decimal
import hashlib
import hmac
import logging
import time
import uuid

import aiohttp

from ...core.types import Order, Symbol, Ticker, Token, Wallet
from ..base import Exchange

BASE_URLS = {"http": "https://api.binance.com/", "wss": "wss://stream.binance.com:443/"}
ENDPOINTS = {
    "listenKey": "api/v3/userDataStream",
    "order": "api/v3/order",
    "account": "api/v3/account",
}

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
        self._receiver_queue = asyncio.Queue()

        asyncio.create_task(self._initialize(api_key))

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
        asyncio.create_task(self._fetch_wallet())
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

    async def _fetch_wallet(self):
        """Fetch account balances."""
        url = BASE_URLS["http"] + ENDPOINTS["account"]

        params = {"omitZeroBalances": "true", "timestamp": int(time.time() * 1000)}
        payload = "&".join(
            [f"{param}={value}" for param, value in sorted(params.items())]
        )
        params["signature"] = self._sign_message(payload)

        async with self._session.get(url, params=params) as resp:
            response = await resp.json()

            for balance in response["balances"]:
                await self._receiver_queue.put(
                    Wallet(balance, Token(balance["asset"]), Decimal(balance["free"]))
                )

    async def _handle_connection(self):
        """Handle websocket connection."""

        async for msg in self._ws_session:
            msg = msg.json()

            if "e" not in msg:
                logger.debug(f"unknown message: {msg}")
                continue

            match msg["e"]:
                case "24hrTicker":
                    await self._handle_ticker(msg)
                case "outboundAccountPosition":
                    await self._handle_wallet(msg)
                case "executionReport":
                    await self._handle_order(msg)
                case _:
                    logger.debug(f"unknown message: {msg}")

    async def _handle_order(self, msg: dict):
        """Handle execution report messages."""
        order = Order(
            msg,
            self._symbols[msg["s"]],
            Decimal(msg["q"]),
            Decimal(msg["p"]),
            msg["S"].lower(),
        )
        await self._receiver_queue.put(order)

    async def _handle_ticker(self, msg: dict):
        """Handle ticker messages."""
        ticker = Ticker(
            msg,
            Decimal(msg["b"]),
            Decimal(msg["B"]),
            Decimal(msg["a"]),
            Decimal(msg["A"]),
        )
        await self._receiver_queue.put(ticker)

    async def _handle_wallet(self, msg: dict):
        """Handle message balances.

        Only balances of the tokens in `Symbol` are sent to the queue. If None,
        send all tokens.

        """
        for balance in msg["B"]:
            await self._receiver_queue.put(
                Wallet(balance, Token(balance["a"]), Decimal(balance["f"]))
            )

    async def subscribe_ticker(self, symbol: Symbol, **_):
        """Subscribe to the ticker."""
        await self._initialized.wait()

        exchange_symbol = f"{symbol.base.name}{symbol.quote.name}".lower()
        payload = {
            "method": "SUBSCRIBE",
            "params": [f"{exchange_symbol}@ticker"],
            "id": str(uuid.uuid4()),
        }
        await self._ws_session.send_json(payload)
        logger.debug(f"Subscription sent for ticker {exchange_symbol}")

    async def buy_market_order(
        self, symbol: Symbol, amount: Decimal, *_args, **_kwargs
    ):
        """Insert a new buy market order."""
        exchange_symbol = f"{symbol.base.name}{symbol.quote.name}"
        self._symbols[exchange_symbol] = symbol
        params = {
            "symbol": exchange_symbol,
            "side": "BUY",
            "type": "MARKET",
            "quantity": str(amount),
            "timestamp": int(time.time() * 1000),  # timestamp in milliseconds
        }
        payload = "&".join([f"{param}={value}" for param, value in params.items()])
        signature = self._sign_message(payload)
        params["signature"] = signature

        logger.info("sending order")
        async with self._session.post(
            BASE_URLS["http"] + ENDPOINTS["order"], params=params
        ) as response:
            await response.json()

    def receiver_queue(self) -> asyncio.Queue:
        """Return the queue containing the messages from the Exchange."""
        return self._receiver_queue

    async def sell_market_order(
        self, symbol: Symbol, amount: Decimal, *_args, **_kwargs
    ):
        """Insert a new sell market order."""
        exchange_symbol = f"{symbol.base.name}{symbol.quote.name}"
        self._symbols[exchange_symbol] = symbol
        params = {
            "symbol": exchange_symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": str(amount),
            "timestamp": int(time.time() * 1000),  # timestamp in milliseconds
        }
        payload = "&".join([f"{param}={value}" for param, value in params.items()])
        signature = self._sign_message(payload)
        params["signature"] = signature

        logger.info("sending order")
        async with self._session.post(
            BASE_URLS["http"] + ENDPOINTS["order"], params=params
        ) as response:
            await response.json()
