"""Define `SimpleAmountStrategy`."""

from decimal import Decimal
from typing import Optional

from ...core.types import Ticker, Wallet
from .base import AmountStrategy


class SimpleAmountStrategy(AmountStrategy):
    """Simple amount strategy calculation.

    Amount is calculated as:
      min(amount, ask, bid, wallet_bid, wallet_ask * ask)
    """

    def __init__(self, trade_amount: Decimal, min_amount: Decimal) -> None:
        self._amount = trade_amount
        self._min_amount = min_amount

    def calculate_amount(
        self, ask: Ticker, bid: Ticker, wallet_ask: Wallet, wallet_bid: Wallet
    ) -> Optional[Decimal]:
        """Return the tradable amount."""
        amount = min(self._amount, ask.ask_amount, bid.bid_amount)
        # Check wallets have enough balance
        # NOTE: `wallet_ask` is the quote token balance. Convert in base
        amount = min(amount, wallet_bid.amount, wallet_ask.amount * ask.ask)

        if amount < self._min_amount:
            return None

        return amount
