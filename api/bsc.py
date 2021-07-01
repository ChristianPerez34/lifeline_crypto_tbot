import json
import time
from decimal import Decimal
from numbers import Real

import aiohttp
from aiogram.utils.markdown import link
from cryptography.fernet import Fernet
from uniswap import Uniswap
from uniswap.exceptions import InsufficientBalance
from uniswap.token import ERC20Token
from uniswap.types import AddressLike
from web3 import Web3
from web3.exceptions import ContractLogicError

from config import BSCSCAN_API_KEY
from config import BUY
from config import FERNET_KEY
from config import HEADERS
from handlers import logger

PANCAKE_SWAP_FACTORY_ADDRESS = Web3.toChecksumAddress(
    "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73")
PANCAKE_SWAP_ROUTER_ADDRESS = Web3.toChecksumAddress(
    "0x10ED43C718714eb63d5aA57B78B54704E256024E")
CONTRACT_ADDRESSES = {
    "BNB": Web3.toChecksumAddress("0x0000000000000000000000000000000000000000"),
    "WBNB": Web3.toChecksumAddress("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
    "BUSD": Web3.toChecksumAddress("0xe9e7cea3dedca5984780bafc599bd69add087d56"),
}
BINANCE_SMART_CHAIN_URL = "https://bsc-dataseed.binance.org/"


class BinanceSmartChain:

    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(BINANCE_SMART_CHAIN_URL))
        self.api_url = "https://api.bscscan.com/api?module=contract&action=getabi&address={address}&apikey={api_key}"
        self.min_pool_size_bnb = 25

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
                "address":
                    self.web3.toChecksumAddress(CONTRACT_ADDRESSES["BNB"]),
                "decimals":
                    18,
            }
        }
        url = (
            f"https://api.bscscan.com/api?module=account&action=tokentx&address={address}&sort=desc&"
            f"apikey={BSCSCAN_API_KEY}")

        async with aiohttp.ClientSession() as session, session.get(
                url, headers=HEADERS) as response:
            data = await response.json()
        bep20_transfers = data["result"]

        for transfer in bep20_transfers:
            account_holdings.update({
                transfer["tokenSymbol"]: {
                    "address":
                        self.web3.toChecksumAddress(transfer["contractAddress"]),
                    "decimals":
                        int(transfer["tokenDecimal"]),
                }
            })
        return account_holdings

    @staticmethod
    def get_decimal_representation(quantity, decimals):
        return quantity / Decimal(10 ** (18 - (decimals % 18)))

    def get_token_balance(self, address: AddressLike, token: AddressLike):
        if token == CONTRACT_ADDRESSES["BNB"]:
            return self.web3.eth.get_balance(address)

        with open('abi/sell.abi') as file:
            abi = json.dumps(json.load(file))
        contract = self.web3.eth.contract(address=token, abi=abi)
        balance = contract.functions.balanceOf(address).call()
        return balance


class PancakeSwap(BinanceSmartChain):

    def __init__(self, address: str, key: str):
        super(PancakeSwap, self).__init__()
        self.address = self.web3.toChecksumAddress(address)
        self.key = key
        self.fernet = Fernet(FERNET_KEY)
        self.pancake_swap = Uniswap(
            self.address,
            self.fernet.decrypt(key.encode()).decode(),
            version=2,
            web3=self.web3,
            factory_contract_addr=PANCAKE_SWAP_FACTORY_ADDRESS,
            router_contract_addr=PANCAKE_SWAP_ROUTER_ADDRESS,
            default_slippage=0.15)

    def get_token(self, address: AddressLike) -> ERC20Token:
        """
        Retrieves metadata from the BEP20 contract of a given token, like its name, symbol, and decimals.
        Args:
            address (AddressLike): Contract address of a given token

        Returns:

        """
        logger.info("Retrieving metadata for token: %s", address)
        return self.pancake_swap.get_token(address=address)

    def swap_tokens(self, token: str, amount_to_spend: Real = 0,
                    side: str = BUY) -> str:
        """
        Swaps crypto coins on PancakeSwap
        Args:
            token (str): Address of coin to buy/sell
            amount_to_spend (float): Amount in BNB expected to spend/receive. When selling will read as percentage
            side (str): Indicates if user wants to buy or sell coins

        Returns: Reply to message

        """
        logger.info("Swapping tokens")
        if self.web3.isConnected():
            token = self.web3.toChecksumAddress(token)
            try:
                if side == BUY:
                    amount_to_spend = self.web3.toWei(amount_to_spend, "ether")
                    txn_hash = self.web3.toHex(
                        self.pancake_swap.make_trade(
                            CONTRACT_ADDRESSES["BNB"],
                            token,
                            amount_to_spend,
                            self.address,
                        ))
                else:
                    balance = self.get_token_balance(address=self.address, token=token)
                    with open('abi/pancakeswap_v2.abi') as pancakeswap_file, open('abi/sell.abi') as sell_file:
                        abi = json.dumps(json.load(pancakeswap_file))
                        sell_abi = json.dumps(json.load(sell_file))
                    contract = self.web3.eth.contract(address=self.pancake_swap.router_address, abi=abi)
                    token_contract = self.web3.eth.contract(address=token, abi=sell_abi)
                    try:
                        max_approval = int('0x000000000000000fffffffffffffffffffffffffffffffffffffffffffffffff', 16)
                        allowance = token_contract.functions.allowance(token, self.pancake_swap.router_address).call()

                        if balance < allowance:
                            approve = token_contract.functions.approve(
                                self.pancake_swap.router_address,
                                max_approval).buildTransaction(
                                {
                                    'from': self.address,
                                    'gasPrice': self.web3.toWei('5', 'gwei'),
                                    'nonce': self.web3.eth.get_transaction_count(self.address),
                                }
                            )

                            signed_txn = self.web3.eth.account.sign_transaction(approve,
                                                                                private_key=self.fernet.decrypt(
                                                                                    self.key.encode()).decode())
                            self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
                            logger.info("Approved token")
                            time.sleep(1)
                        txn = contract.functions.swapExactTokensForETH(
                            balance, 0,
                            [token, CONTRACT_ADDRESSES['WBNB']],
                            self.address,
                            (int(time.time()) + 1000000)

                        ).buildTransaction({
                            'from': self.address,
                            'gasPrice': self.web3.toWei('6', 'gwei'),
                            'nonce': self.web3.eth.get_transaction_count(self.address),
                        })
                    except ContractLogicError as e:
                        logger.exception(e)
                        logger.info("Attempting sell with swapExactTokensForETHSupportingFeeOnTransferTokens function")
                        txn = contract.functions.swapExactTokensForETHSupportingFeeOnTransferTokens(
                            balance, 0,
                            [token, CONTRACT_ADDRESSES['WBNB']],
                            self.address,
                            (int(time.time()) + 1000000)

                        ).buildTransaction({
                            'from': self.address,
                            'gasPrice': self.web3.toWei('5', 'gwei'),
                            'nonce': self.web3.eth.get_transaction_count(self.address),
                        })

                    signed_txn = self.web3.eth.account.sign_transaction(txn, private_key=self.fernet.decrypt(
                        self.key.encode()).decode())
                    txn_hash = self.web3.toHex(self.web3.eth.send_raw_transaction(signed_txn.rawTransaction))

                txn_hash_url = f"https://bscscan.com/tx/{txn_hash}"
                reply = f"Transactions completed successfully. {link(title='View Transaction', url=txn_hash_url)}"
            except InsufficientBalance as e:
                logger.exception(e)
                reply = (
                    "⚠️ Insufficient balance. Top up your token balance and try again. "
                )
        else:
            logger.info("Unable to connect to Binance Smart Chain")
            reply = "⚠ Sorry, I was unable to connect to the Binance Smart Chain. Try again later."
        return reply

    def get_token_price(self, token: AddressLike) -> Decimal:
        """
        Gets token price in BUSD
        Args:
            token (AddressLike): Contract Address of coin

        Returns (Decimal): Token price in BUSD

        """
        logger.info("Retrieving token price in BUSD for %s", token)
        busd = self.web3.toChecksumAddress(CONTRACT_ADDRESSES["BUSD"])
        token_per_busd = Decimal(
            self.pancake_swap.get_price_input(busd, token, 10 ** 18))
        return token_per_busd
