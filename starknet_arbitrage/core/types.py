"""Bot custom types."""

from dataclasses import dataclass
from decimal import Decimal

from ccxt.base.types import Ticker as cTicker


@dataclass
class Symbol:
    base: str
    quote: str


@dataclass
class Ticker:
    raw: cTicker
    bid: Decimal
    bid_amount: Decimal
    ask: Decimal
    ask_amount: Decimal
