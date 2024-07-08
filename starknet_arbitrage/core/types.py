"""Bot custom types."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Token:
    name: str
    address: str
    decimals: int


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
