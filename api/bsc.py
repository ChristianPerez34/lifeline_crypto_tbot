from decimal import Decimal
from typing import Union

import aiohttp
from aiogram.utils.markdown import link
from cryptography.fernet import Fernet
from pandas import DataFrame
from web3 import Web3
from web3.exceptions import ContractLogicError, BadFunctionCallOutput
from web3.types import Wei, Address, ChecksumAddress

from api.eth import ERC20Like
from app import logger
from config import BSCSCAN_API_KEY, BUY, FERNET_KEY, HEADERS

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
        self.factory_address = self.web3.toChecksumAddress(
            "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
        )
        self.router_address = self.web3.toChecksumAddress(
            "0x10ED43C718714eb63d5aA57B78B54704E256024E"
        )

    async def get_account_token_holdings(
        self, address: Union[Address, ChecksumAddress, str] = None
    ) -> DataFrame:
        """
        Retrieves account holding for wallet address
        Args:
            address (AddressLike): Wallet address of user

        Returns (dict): User account holdings

        """
        if not address:
            address = self.address
        logger.info("Gathering account holdings for %s", address)
        account_holdings = []
        holdings = {
            "BNB": {
                "address": self.web3.toChecksumAddress(CONTRACT_ADDRESSES["BNB"]),
                "decimals": 18,
            }
        }
        url = (
            f"https://api.bscscan.com/api?module=account&action=tokentx&address={address}&sort=desc&"  # type: ignore
            f"apikey={BSCSCAN_API_KEY}"
        )

        async with aiohttp.ClientSession() as session, session.get(
            url, headers=HEADERS
        ) as response:
            data = await response.json()
        bep20_transfers = data["result"]

        for transfer in bep20_transfers:
            holdings.update(
                {
                    transfer["tokenSymbol"]: {
                        "address": self.web3.toChecksumAddress(
                            transfer["contractAddress"]
                        ),
                        "decimals": int(transfer["tokenDecimal"]),
                    }
                }
            )
        for key, value in holdings.items():
            coin = value
            token = coin["address"]
            token_decimals = coin["decimals"]

            # Quantity in wei used to calculate price
            quantity = await self.get_token_balance(address=self.address, token=token)

            if quantity > 0:
                try:
                    token_price = await self.get_token_price(
                        token=token, decimals=token_decimals
                    )

                    # Quantity in correct format as seen in wallet
                    quantity = self.get_decimal_representation(
                        quantity=quantity, decimals=coin["decimals"]
                    )
                    price = quantity * token_price
                    usd_amount = price.quantize(Decimal("0.01"))
                    account_holdings.append(
                        {"Symbol": key, "Balance": quantity, "USD": usd_amount}
                    )

                except (ContractLogicError, BadFunctionCallOutput) as e:
                    logger.exception(e)
        return DataFrame(account_holdings)

    async def get_token_balance(
        self,
        address: Union[Address, ChecksumAddress, str],
        token: Union[Address, ChecksumAddress, str],
    ) -> Wei:
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

        abi = await self.get_contract_abi(abi_type="sell")
        contract = self.web3.eth.contract(address=token, abi=abi)
        return contract.functions.balanceOf(address).call()

    async def get_token_price(self, token, decimals):
        raise NotImplementedError


class PancakeSwap(BinanceSmartChain):
    def __init__(self, address: str, key: str):
        super(PancakeSwap, self).__init__()
        self.address = self.web3.toChecksumAddress(address)
        self.key = key
        self.fernet = Fernet(FERNET_KEY)

    async def swap_tokens(
        self,
        token: str,
        amount_to_spend: Union[int, float, Decimal] = 0,
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
                abi = await self.get_contract_abi(abi_type="router")
                token_abi = await self.get_contract_abi(abi_type="sell")
                contract = self.web3.eth.contract(address=self.router_address, abi=abi)
                token_contract = self.web3.eth.contract(address=token, abi=token_abi)

                if side == BUY:
                    amount_to_spend = self.web3.toWei(amount_to_spend, "ether")
                    route = [wbnb, token]
                    args = (contract, route, amount_to_spend, gas_price)
                    swap_methods = [
                        self._swap_exact_eth_for_tokens,
                        self._swap_exact_eth_for_tokens_supporting_fee_on_transfer_tokens,
                    ]
                    balance = await self.get_token_balance(
                        address=self.address, token=CONTRACT_ADDRESSES["BNB"]
                    )
                else:
                    amount_to_spend = await self.get_token_balance(
                        address=self.address, token=token  # type: ignore
                    )
                    route = [token, CONTRACT_ADDRESSES["WBNB"]]
                    args = (contract, route, amount_to_spend, gas_price)
                    swap_methods = [
                        self._swap_exact_tokens_for_eth,
                        self._swap_exact_tokens_for_eth_supporting_fee_on_transfer_tokens,
                    ]
                    balance = await self.get_token_balance(address=self.address, token=token)  # type: ignore
                    await self._check_approval(
                        contract=token_contract,
                        token=token,
                        balance=balance,
                    )

                if balance < amount_to_spend:
                    raise ValueError(
                        f"Insufficient balance. Had {balance}, needed {amount_to_spend}"
                    )

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
                await self._check_approval(
                    contract=token_contract,
                    token=token,
                    balance=self.get_token_balance(address=self.address, token=token),  # type: ignore
                )
            except ValueError as e:
                logger.exception(e)
                reply = str(e)
        else:
            logger.info("Unable to connect to Binance Smart Chain")
            reply = "⚠ Sorry, I was unable to connect to the Binance Smart Chain. Try again later."
        return reply

    async def get_token_price(
        self, token: Union[Address, ChecksumAddress, str], decimals: int = 18
    ) -> Decimal:
        """
        Gets token price in BUSD
        Args:
            token (AddressLike): Contract Address of coin
            decimals (int): Token decimals

        Returns (Decimal): Token price in BUSD

        """
        logger.info("Retrieving token price in BUSD for %s", token)

        await self.set_router_contract()
        busd = CONTRACT_ADDRESSES["BUSD"]
        bnb = CONTRACT_ADDRESSES["BNB"]
        wbnb = CONTRACT_ADDRESSES["WBNB"]

        route = [busd, wbnb, token] if token not in (bnb, wbnb) else [busd, bnb]
        qty = 10 ** decimals

        try:
            token_price = self.web3.fromWei(
                self.router_contract.functions.getAmountsIn(qty, route).call()[0],
                "ether",
            )
        except ContractLogicError:
            token_price = 0
        return token_price

    async def get_token_pair_address(
        self,
        token_0: Union[Address, ChecksumAddress, str],
        token_1: Union[Address, ChecksumAddress, str] = CONTRACT_ADDRESSES["WBNB"],
    ) -> str:
        """
        Retrieves token pair address
        Args:
            token_0: BEP20 token address
            token_1: BEP20 token address

        Returns: Pair address

        """
        await self.set_factory_contract()
        return self.factory_contract.functions.getPair(token_0, token_1).call()
