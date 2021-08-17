import json
from decimal import Decimal

from cryptography.fernet import Fernet
from uniswap import Uniswap
from uniswap.types import AddressLike
from web3 import Web3
from web3.types import Wei

from app import logger
from config import FERNET_KEY, ETHEREUM_MAIN_NET_URL
from handlers import ether_scan

CONTRACT_ADDRESSES = {
    "ETH": Web3.toChecksumAddress("0x0000000000000000000000000000000000000000"),
    "WETH": Web3.toChecksumAddress("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    "USDC": Web3.toChecksumAddress("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
}


class ERC20Like:

    @staticmethod
    def get_decimal_representation(quantity: Decimal, decimals: int) -> Decimal:
        """
        Decimal representation of inputted quantity
        Args:
            quantity (Decimal): Amount to convert to decimal representation
            decimals (int): Amount of decimals for token contract

        Returns: Decimal/Normalized representation of inputted quantity
        """
        if decimals < 9:
            decimals += 2
        return quantity / Decimal(10 ** (18 - (decimals % 18)))

    @staticmethod
    def get_contract_abi(abi_type: str = "liquidity") -> str:
        """
        Retrieves contract abi
        Args:
            abi_type (str): Type of abi to use

        Returns (str): Abi string

        """
        logger.info("Retrieving contract abi for type: %s", abi_type)
        filename = "abi/pancake_swap_liquidity_v2.abi"

        if abi_type == "sell":
            filename = "abi/sell.abi"
        elif abi_type == "router":
            filename = "abi/pancakeswap_v2.abi"
        with open(filename) as file:
            abi = json.dumps(json.load(file))
        return abi


class EthereumChain(ERC20Like):
    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(ETHEREUM_MAIN_NET_URL))
        # self.api_url = "https://api.bscscan.com/api?module=contract&action=getabi&address={address}&apikey={api_key}"
        # self.min_pool_size_bnb = 25

    async def get_account_token_holdings(self, address: AddressLike) -> dict:
        """
        Retrieves account holding for wallet address
        Args:
            address (AddressLike): Wallet address of user

        Returns (dict): User account holdings

        """
        logger.info("Gathering account holdings for %s", address)
        account_holdings = {
            "ETH": {
                "address": self.web3.toChecksumAddress(CONTRACT_ADDRESSES["ETH"]),
                "decimals": 18,
            }
        }

        erc20_transfers = ether_scan.get_erc20_token_transfer_events_by_address(
            address=address,
            startblock=0, endblock=99999999, sort='desc')

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
        if token == CONTRACT_ADDRESSES["ETH"]:
            return self.web3.eth.get_balance(address)

        abi = self.get_contract_abi(abi_type="sell")
        contract = self.web3.eth.contract(address=token, abi=abi)
        return contract.functions.balanceOf(address).call()


class UniSwap(EthereumChain):
    def __init__(self, address: str, key: str):
        super(UniSwap, self).__init__()
        self.address = self.web3.toChecksumAddress(address)
        self.key = key
        self.fernet = Fernet(FERNET_KEY)
        self.dex = Uniswap(
            self.address,
            self.fernet.decrypt(key.encode()).decode(),
            version=2,
            web3=self.web3,
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
