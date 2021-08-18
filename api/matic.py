from decimal import Decimal
from typing import Union

import aiohttp
import requests
from aiogram.utils.markdown import link
from cryptography.fernet import Fernet
from uniswap import Uniswap
from uniswap.exceptions import InsufficientBalance
from uniswap.types import AddressLike
from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.types import Wei

from api.eth import ERC20Like
from app import logger
from config import FERNET_KEY, POLYGONSCAN_API_KEY, HEADERS, BUY

QUICK_SWAP_FACTORY_ADDRESS = Web3.toChecksumAddress(
    "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32"
)
QUICK_SWAP_ROUTER_ADDRESS = Web3.toChecksumAddress(
    "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
)
CONTRACT_ADDRESSES = {
    "MATIC": Web3.toChecksumAddress("0x0000000000000000000000000000000000000000"),
    "WMATIC": Web3.toChecksumAddress("0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270"),
    "USDC": Web3.toChecksumAddress("0x2791bca1f2de4661ed88a30c99a7a9449aa84174"),
}

AVERAGE_TRANSACTION_SPEED = "standard"
FAST_TRANSACTION_SPEED = "fastest"

TRANSACTION_SPEEDS = {
    "slow": "safeLow",
    "average": "standard",
    "fast": "fast",
    "fastest": "fastest",
}

MATIC_CHAIN_URL = "https://rpc-mainnet.matic.network"


class PolygonChain(ERC20Like):
    def __init__(self):
        super(PolygonChain, self).__init__()
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


class QuickSwap(PolygonChain):
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
            router_contract_addr=QUICK_SWAP_ROUTER_ADDRESS,
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

    def get_gas_price(self, speed: str):
        gas_prices = requests.get(
            "https://gasstation-mainnet.matic.network/", timeout=5
        ).json()
        return gas_prices[TRANSACTION_SPEEDS[speed]]

    def swap_tokens(
        self,
        token: str,
        amount_to_spend: Union[int, float, str, Decimal] = 0,
        side: str = BUY,
        is_snipe: bool = False,
    ) -> str:
        """
        Swaps crypto coins on PancakeSwap
        Args:
            token (str): Address of coin to buy/sell
            amount_to_spend (float): Amount in BNB expected to spend/receive. When selling will read as percentage
            side (str): Indicates if user wants to buy or sell coins
            is_snipe (bool): Indicates if swap is for sniping. Utilizes increasingly high gas price to ensure buying
                token as soon as possible

        Returns: Reply to message

        """
        logger.info("Swapping tokens")
        if self.web3.isConnected():
            token = self.web3.toChecksumAddress(token)
            wmatic = CONTRACT_ADDRESSES["WMATIC"]
            gas_price = (
                self.web3.toWei(
                    self.get_gas_price(speed=AVERAGE_TRANSACTION_SPEED), "gwei"
                )
                if not is_snipe
                else self.web3.toWei(
                    self.get_gas_price(speed=FAST_TRANSACTION_SPEED), "gwei"
                )
            )
            try:
                txn = None
                abi = self.get_contract_abi(abi_type="router")
                contract = self.web3.eth.contract(
                    address=self.dex.router_address, abi=abi
                )
                if side == BUY:
                    amount_to_spend = self.web3.toWei(amount_to_spend, "ether")
                    route = [wmatic, token]
                    args = (contract, route, amount_to_spend, gas_price)
                    swap_methods = [
                        self._swap_exact_eth_for_tokens,
                        self._swap_exact_eth_for_tokens_supporting_fee_on_transfer_tokens,
                    ]
                    balance = self.get_token_balance(
                        address=self.address, token=CONTRACT_ADDRESSES["MATIC"]
                    )
                else:
                    token_abi = self.get_contract_abi(abi_type="sell")
                    token_contract = self.web3.eth.contract(
                        address=token, abi=token_abi
                    )
                    amount_to_spend = self.get_token_balance(
                        address=self.address, token=token
                    )
                    route = [token, CONTRACT_ADDRESSES["WMATIC"]]
                    args = (contract, route, amount_to_spend, gas_price)
                    swap_methods = [
                        self._swap_exact_tokens_for_eth,
                        self._swap_exact_tokens_for_eth_supporting_fee_on_transfer_tokens,
                    ]
                    balance = self.get_token_balance(address=self.address, token=token)
                    self._check_approval(contract=token_contract, token=token)

                if balance < amount_to_spend:
                    raise InsufficientBalance(had=balance, needed=amount_to_spend)

                for swap_method in swap_methods:
                    try:
                        txn = swap_method(*args)
                        break
                    except ContractLogicError as e:
                        logger.exception(e)

                signed_txn = self.web3.eth.account.sign_transaction(
                    txn, private_key=self.fernet.decrypt(self.key.encode()).decode()
                )
                txn_hash = self.web3.toHex(
                    self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
                )
                logger.info("Transaction completed successfully")
                txn_hash_url = f"https://polygonscan.com/tx/{txn_hash}"
                reply = f"Transactions completed successfully. {link(title='View Transaction', url=txn_hash_url)}"
            except InsufficientBalance as e:
                logger.exception(e)
                reply = (
                    "⚠️ Insufficient balance. Top up your token balance and try again. "
                )
            except ValueError as e:
                logger.exception(e)
                reply = e.args[0]["message"]
        else:
            logger.info("Unable to connect to Polygon Network")
            reply = "⚠ Sorry, I was unable to connect to the Polygon Network. Try again later."
        return reply
