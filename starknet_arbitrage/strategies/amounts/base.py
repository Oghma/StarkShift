"""Define the `AmountStrategy` interface."""

import abc
from decimal import Decimal
from typing import Optional

from ...core.types import Ticker, Wallet


class AmountStrategy(abc.ABC):
    """Interface for amount calculation strategies."""

    @abc.abstractmethod
    def calculate_amount(
        self, ask: Ticker, bid: Ticker, wallet_ask: Wallet, wallet_bid: Wallet
    ) -> Optional[Decimal]:
        """Return the tradable amount."""
