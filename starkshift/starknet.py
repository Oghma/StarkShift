"""`Starknet` handles the communication with the chain."""

from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.models.chains import StarknetChainId
from starknet_py.net.signer.stark_curve_signer import KeyPair


class Starknet:

    def __init__(self, node_url: str, testnet: bool = False) -> None:
        self._chain_handle = FullNodeClient(node_url)
        self._testnet = testnet

    def get_account(self, address: str, signer_key: str) -> Account:
        """Return the account associated to the address"""
        key_pair = KeyPair.from_private_key(signer_key)
        chain = StarknetChainId.SEPOLIA if self._testnet else StarknetChainId.MAINNET

        return Account(
            client=self._chain_handle,
            address=address,
            key_pair=key_pair,
            chain=chain,
        )
