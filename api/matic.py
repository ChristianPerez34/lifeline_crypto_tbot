from decimal import Decimal

import aiohttp
from cryptography.fernet import Fernet
from uniswap import Uniswap
from uniswap.types import AddressLike
from web3 import Web3
from web3.types import Wei

from api.eth import ERC20Like
from app import logger
from config import FERNET_KEY, POLYGONSCAN_API_KEY, HEADERS

QUICK_SWAP_FACTORY_ADDRESS = Web3.toChecksumAddress(
    "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32"
)
QUICK_SWAP_ROUTER_ADDRESS = Web3.toChecksumAddress(
    "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
)
CONTRACT_ADDRESSES = {
    "MATIC": Web3.toChecksumAddress("0x0000000000000000000000000000000000000000"),
    "WMATIC": Web3.toChecksumAddress("0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270"),
    "USDC": Web3.toChecksumAddress("0x2791bca1f2de4661ed88a30c99a7a9449aa84174")
}

MATIC_CHAIN_URL = "https://rpc-mainnet.matic.network"


class MaticChain(ERC20Like):
    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(MATIC_CHAIN_URL))

    async def get_account_token_holdings(self, address: AddressLike) -> dict:
        """
        Retrieves account holding for wallet address
        Args:
            address (AddressLike): Wallet address of user

        Returns (dict): User account holdings

        """
        logger.info("Gathering account holdings for %s", address)
        account_holdings = {
            "MATIC": {
                "address": self.web3.toChecksumAddress(CONTRACT_ADDRESSES["MATIC"]),
                "decimals": 18,
            }
        }

        url = (
            f"https://api.polygonscan.com/api?module=account&action=tokentx&address={address}&sort=desc&"
            f"apikey={POLYGONSCAN_API_KEY}"
        )

        async with aiohttp.ClientSession() as session, session.get(
                url, headers=HEADERS
        ) as response:
            data = await response.json()
        erc20_transfers = data["result"]

        for transfer in erc20_transfers:
            account_holdings.update(
                {
                    transfer["tokenSymbol"]: {
                        "address": self.web3.toChecksumAddress(
                            transfer["contractAddress"]
                        ),
                        "decimals": int(transfer["tokenDecimal"]),
                    }
                }
            )
        return account_holdings

    def get_token_balance(self, address: AddressLike, token: AddressLike) -> Wei:
        """
        Retrieves amount of tokens in address
        Args:
            address (AddressLike): Wallet address
            token (AddressLike): Token Contract Address

        Returns (Wei): Token balance in wallet

        """
        logger.info("Retrieving token balance for %s", address)
        if token == CONTRACT_ADDRESSES["MATIC"]:
            return self.web3.eth.get_balance(address)

        abi = self.get_contract_abi(abi_type="sell")
        contract = self.web3.eth.contract(address=token, abi=abi)
        return contract.functions.balanceOf(address).call()


class QuickSwap(MaticChain):
    def __init__(self, address: str, key: str):
        super(QuickSwap, self).__init__()
        self.address = self.web3.toChecksumAddress(address)
        self.key = key
        self.fernet = Fernet(FERNET_KEY)
        self.dex = Uniswap(
            self.address,
            self.fernet.decrypt(key.encode()).decode(),
            version=2,
            web3=self.web3,
            factory_contract_addr=QUICK_SWAP_FACTORY_ADDRESS,
            router_contract_addr=QUICK_SWAP_ROUTER_ADDRESS
        )

    def get_token_price(
            self, token: AddressLike, as_usdc_per_token: bool = False
    ) -> Decimal:
        """
        Gets token price in USDC
        Args:
            token (AddressLike): Contract Address of coin
            as_usdc_per_token (bool): Determines if output should be USDC per token or token per USDC

        Returns (Decimal): Tokens per USDC / USDC per tokens

        """
        logger.info("Retrieving token price in USDC for %s", token)
        usdc = CONTRACT_ADDRESSES["USDC"]
        return (
            Decimal(self.dex.get_price_output(usdc, token, 10 ** 6))
            if as_usdc_per_token
            else Decimal(self.dex.get_price_input(usdc, token, 10 ** 6))
        )
