"""Bot custom types."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Token:
    name: str
    address: str
    decimals: int

    def __str__(self) -> str:
        return f"{type(self).__name__}(name={self.name})"


@dataclass
class Symbol:
    base: Token
    quote: Token


@dataclass
class Ticker:
    raw: dict
    bid: Decimal
    bid_amount: Decimal
    ask: Decimal
    ask_amount: Decimal


@dataclass
class Wallet:
    raw: dict
    token: Token
    amount: Decimal

    def __str__(self) -> str:
        return f"{type(self).__name__}(token={self.token}, amount={self.amount})"

    @staticmethod
    def empty(token: Token) -> Wallet:
        return Wallet({}, token, Decimal(0))


@dataclass
class Order:
    raw: dict
    symbol: Symbol
    amount: Decimal
    price: Decimal
    order: str
