from decimal import Decimal

from aiogram.utils.markdown import link
from cryptography.fernet import Fernet
from uniswap import InsufficientBalance
from uniswap import Uniswap
from web3 import Web3

from config import BUY
from config import FERNET_KEY

PANCAKESWAP_FACTORY_ADDRESS = Web3.toChecksumAddress(
    "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73")
PANCAKESWAP_ROUTER_ADDRESS = Web3.toChecksumAddress(
    "0x10ED43C718714eb63d5aA57B78B54704E256024E")
BNB_ADDRESS = "0x0000000000000000000000000000000000000000"
BINANCE_SMART_CHAIN_URL = "https://bsc-dataseed.binance.org/"
BSCSCAN_API_URL = "https://api.bscscan.com/api?module=contract&action=getabi&address={address}&apikey={api_key}"
MAX_SLIPPAGE = 0.15

GAS = 250000
GAS_PRICE = Web3.toWei("10", "gwei")


class BinanceSmartChain:
    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(BINANCE_SMART_CHAIN_URL))

    def get_account_balance(self, address: str) -> Decimal:
        return self.web3.fromWei(self.web3.eth.get_balance(address), "ether")


class PancakeSwap(BinanceSmartChain):
    def __init__(self, address: str, key: str):
        super(PancakeSwap, self).__init__()
        self.address = address
        self.key = key
        self.fernet = Fernet(FERNET_KEY)
        self.pancake_swap = Uniswap(
            self.address,
            self.fernet.decrypt(key.encode()).decode(),
            version=2,
            web3=self.web3,
            factory_contract_addr=PANCAKESWAP_FACTORY_ADDRESS,
            router_contract_addr=PANCAKESWAP_ROUTER_ADDRESS,
            max_slippage=MAX_SLIPPAGE,
        )

    def swap_tokens(self, token: str, amount_to_spend: Decimal,
                    side: str) -> str:
        """
        Swaps crypto coins on PancakeSwap
        Args:
            token (str): Address of coin to buy/sell
            amount_to_spend (float): Amount in BNB expected to spend/receive. When selling will read as percentage
            side (str): Indicates if user wants to buy or sell coins

        Returns: Reply to message

        """

        if self.web3.isConnected():
            token = self.web3.toChecksumAddress(token)
            try:
                if side == BUY:
                    amount_to_spend = self.web3.toWei(amount_to_spend, "ether")
                    txn_hash = self.web3.toHex(
                        self.pancake_swap.make_trade(BNB_ADDRESS, token,
                                                     amount_to_spend,
                                                     self.address))
                else:
                    balance = self.web3.fromWei(
                        self.pancake_swap.get_token_balance(token), "ether")
                    amount_to_spend = self.web3.toWei(
                        balance * amount_to_spend, "ether")
                    txn_hash = self.web3.toHex(
                        self.pancake_swap.make_trade_output(
                            token, BNB_ADDRESS, amount_to_spend, self.address))

                txn_hash_url = f"https://bscscan.com/tx/{txn_hash}"
                reply = f"Transactions completed successfully. {link(title='View Transaction', url=txn_hash_url)}"
            except InsufficientBalance:
                reply = (
                    "⚠️ Insufficient balance. Top up you BNB balance and try again. "
                )
        else:
            reply = "⚠ Sorry, I was unable to connect to the Binance Smart Chain. Try again later."
        return reply
