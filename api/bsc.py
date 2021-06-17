from decimal import Decimal

import aiohttp
from aiogram.utils.markdown import link
from cryptography.fernet import Fernet
from uniswap import Uniswap
from uniswap.exceptions import InsufficientBalance
from web3 import Web3

from config import BSCSCAN_API_KEY, BUY, FERNET_KEY, HEADERS

PANCAKE_SWAP_FACTORY_ADDRESS = Web3.toChecksumAddress(
    "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
)
PANCAKE_SWAP_ROUTER_ADDRESS = Web3.toChecksumAddress(
    "0x10ED43C718714eb63d5aA57B78B54704E256024E"
)
CONTRACT_ADDRESSES = {
    "BNB": "0x0000000000000000000000000000000000000000",
    "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    "BUSD": "0xe9e7cea3dedca5984780bafc599bd69add087d56",
}
BINANCE_SMART_CHAIN_URL = "https://bsc-dataseed.binance.org/"


class BinanceSmartChain:
    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(BINANCE_SMART_CHAIN_URL))
        self.api_url = "https://api.bscscan.com/api?module=contract&action=getabi&address={address}&apikey={api_key}"
        self.min_pool_size_bnb = 25

    def get_account_balance(self, address: str) -> Decimal:
        return self.web3.fromWei(self.web3.eth.get_balance(address), "ether")

    async def get_account_token_holdings(self, address):
        account_holdings = {
            "BNB": {
                "address": self.web3.toChecksumAddress(CONTRACT_ADDRESSES["BNB"]),
                "decimals": 18,
            }
        }
        url = f"https://api.bscscan.com/api?module=account&action=tokentx&address={address}&sort=desc&apikey={BSCSCAN_API_KEY}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS) as response:
                json = await response.json()
        bep20_transfers = json["result"]

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
            factory_contract_addr=PANCAKE_SWAP_FACTORY_ADDRESS,
            router_contract_addr=PANCAKE_SWAP_ROUTER_ADDRESS,
        )

    def get_token(self, address):
        return self.pancake_swap.get_token(address=address)

    def get_token_balance(self, token) -> int:
        return self.pancake_swap.get_token_balance(token)

    def swap_tokens(self, token: str, amount_to_spend: Decimal, side: str) -> str:
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
                        self.pancake_swap.make_trade(
                            CONTRACT_ADDRESSES["BNB"],
                            token,
                            amount_to_spend,
                            self.address,
                        )
                    )
                else:
                    balance = self.web3.fromWei(self.get_token_balance(token), "ether")
                    amount_to_spend = self.web3.toWei(
                        balance * amount_to_spend, "ether"
                    )
                    txn_hash = self.web3.toHex(
                        self.pancake_swap.make_trade_output(
                            token,
                            CONTRACT_ADDRESSES["BNB"],
                            amount_to_spend,
                            self.address,
                        )
                    )

                txn_hash_url = f"https://bscscan.com/tx/{txn_hash}"
                reply = f"Transactions completed successfully. {link(title='View Transaction', url=txn_hash_url)}"
            except InsufficientBalance:
                reply = (
                    "⚠️ Insufficient balance. Top up you BNB balance and try again. "
                )
        else:
            reply = "⚠ Sorry, I was unable to connect to the Binance Smart Chain. Try again later."
        return reply

    def get_token_price(self, address):
        busd = self.web3.toChecksumAddress(CONTRACT_ADDRESSES["BUSD"])
        token_per_busd = Decimal(
            self.pancake_swap.get_price_input(busd, address, 10 ** 18)
        )
        return token_per_busd
