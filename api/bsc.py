from decimal import Decimal
from typing import Union

import aiohttp
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
from config import BSCSCAN_API_KEY, BUY, FERNET_KEY, HEADERS

PANCAKE_SWAP_FACTORY_ADDRESS = Web3.toChecksumAddress(
    "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
)
PANCAKE_SWAP_ROUTER_ADDRESS = Web3.toChecksumAddress(
    "0x10ED43C718714eb63d5aA57B78B54704E256024E"
)
CONTRACT_ADDRESSES = {
    "BNB": Web3.toChecksumAddress("0x0000000000000000000000000000000000000000"),
    "WBNB": Web3.toChecksumAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
    "BUSD": Web3.toChecksumAddress("0xe9e7cea3dedca5984780bafc599bd69add087d56"),
}
BINANCE_SMART_CHAIN_URL = "https://bsc-dataseed.binance.org/"


class BinanceSmartChain(ERC20Like):
    def __init__(self):
        super(BinanceSmartChain, self).__init__()
        self.web3 = Web3(
            Web3.HTTPProvider(BINANCE_SMART_CHAIN_URL, request_kwargs={"timeout": 60})
        )

    async def get_account_token_holdings(self, address: AddressLike) -> dict:
        """
        Retrieves account holding for wallet address
        Args:
            address (AddressLike): Wallet address of user

        Returns (dict): User account holdings

        """
        logger.info("Gathering account holdings for %s", address)
        account_holdings = {
            "BNB": {
                "address": self.web3.toChecksumAddress(CONTRACT_ADDRESSES["BNB"]),
                "decimals": 18,
            }
        }
        url = (
            f"https://api.bscscan.com/api?module=account&action=tokentx&address={address}&sort=desc&"
            f"apikey={BSCSCAN_API_KEY}"
        )

        async with aiohttp.ClientSession() as session, session.get(
            url, headers=HEADERS
        ) as response:
            data = await response.json()
        bep20_transfers = data["result"]

        for transfer in bep20_transfers:
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
        if token == CONTRACT_ADDRESSES["BNB"]:
            return self.web3.eth.get_balance(address)

        abi = self.get_contract_abi(abi_type="sell")
        contract = self.web3.eth.contract(address=token, abi=abi)
        return contract.functions.balanceOf(address).call()


class PancakeSwap(BinanceSmartChain):
    def __init__(self, address: str, key: str):
        super(PancakeSwap, self).__init__()
        self.address = self.web3.toChecksumAddress(address)
        self.key = key
        self.fernet = Fernet(FERNET_KEY)
        self.dex = Uniswap(
            self.address,
            self.fernet.decrypt(key.encode()).decode(),
            version=2,
            web3=self.web3,
            factory_contract_addr=PANCAKE_SWAP_FACTORY_ADDRESS,
            router_contract_addr=PANCAKE_SWAP_ROUTER_ADDRESS,
            default_slippage=0.15,
        )

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
            wbnb = CONTRACT_ADDRESSES["WBNB"]
            gas_price = (
                self.web3.toWei("5", "gwei")
                if not is_snipe
                else self.web3.toWei("65", "gwei")
            )
            try:
                txn = None
                abi = self.get_contract_abi(abi_type="router")
                token_abi = self.get_contract_abi(abi_type="sell")
                contract = self.web3.eth.contract(
                    address=self.dex.router_address, abi=abi
                )
                token_contract = self.web3.eth.contract(address=token, abi=token_abi)

                if side == BUY:
                    amount_to_spend = self.web3.toWei(amount_to_spend, "ether")
                    route = [wbnb, token]
                    args = (contract, route, amount_to_spend, gas_price)
                    swap_methods = [
                        self._swap_exact_eth_for_tokens,
                        self._swap_exact_eth_for_tokens_supporting_fee_on_transfer_tokens,
                    ]
                    balance = self.get_token_balance(
                        address=self.address, token=CONTRACT_ADDRESSES["BNB"]
                    )
                else:
                    amount_to_spend = self.get_token_balance(
                        address=self.address, token=token
                    )
                    route = [token, CONTRACT_ADDRESSES["WBNB"]]
                    args = (contract, route, amount_to_spend, gas_price)
                    swap_methods = [
                        self._swap_exact_tokens_for_eth,
                        self._swap_exact_tokens_for_eth_supporting_fee_on_transfer_tokens,
                    ]
                    balance = self.get_token_balance(address=self.address, token=token)
                    self._check_approval(
                        contract=token_contract,
                        token=token,
                        balance=balance,
                    )

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
                txn_hash_url = f"https://bscscan.com/tx/{txn_hash}"
                reply = f"Transactions completed successfully. {link(title='View Transaction', url=txn_hash_url)}"

                # Pre-approve token for future swaps
                self.web3.eth.waitForTransactionReceipt(txn_hash, timeout=6000)
                self._check_approval(
                    contract=token_contract,
                    token=token,
                    balance=self.get_token_balance(address=self.address, token=token),
                )
            except InsufficientBalance as e:
                logger.exception(e)
                reply = (
                    "⚠️ Insufficient balance. Top up your token balance and try again. "
                )
            except ValueError as e:
                logger.exception(e)
                reply = e.args[0]["message"]
        else:
            logger.info("Unable to connect to Binance Smart Chain")
            reply = "⚠ Sorry, I was unable to connect to the Binance Smart Chain. Try again later."
        return reply

    def get_token_price(self, token: AddressLike, decimals: int = 18) -> Decimal:
        """
        Gets token price in BUSD
        Args:
            token (AddressLike): Contract Address of coin
            decimals (int): Token decimals

        Returns (Decimal): Token price in BUSD

        """
        logger.info("Retrieving token price in BUSD for %s", token)
        busd = CONTRACT_ADDRESSES["BUSD"]

        return self.web3.fromWei(
            self.dex.get_price_output(busd, token, 10 ** decimals), "ether"
        )

    def get_token_pair_address(
        self, token_0: AddressLike, token_1: AddressLike = CONTRACT_ADDRESSES["WBNB"]
    ) -> str:
        """
        Retrieves token pair address
        Args:
            token: BEP20 token

        Returns: Pair address

        """
        contract = self.dex.factory_contract
        return contract.functions.getPair(token_0, token_1).call()
