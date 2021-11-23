import json
import time
from decimal import Decimal
from typing import Union

import aiofiles
import aiohttp
from aiogram.utils.markdown import link
from cryptography.fernet import Fernet
from pandas import DataFrame
from pydantic.main import BaseModel
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError, BadFunctionCallOutput
from web3.types import Address, ChecksumAddress
from web3.types import Wei, TxParams

from app import logger
from config import FERNET_KEY, ETHEREUM_MAIN_NET_URL, BUY, ETHERSCAN_API_KEY
from handlers import gas_tracker

CONTRACT_ADDRESSES = {
    "ETH": Web3.toChecksumAddress("0x0000000000000000000000000000000000000000"),
    "WETH": Web3.toChecksumAddress("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    "USDC": Web3.toChecksumAddress("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"),
}

AVERAGE_TRANSACTION_SPEED = "fast"
FAST_TRANSACTION_SPEED = "fastest"


class ERC20Token(BaseModel):
    name: str
    symbol: str
    decimals: int
    network: str
    address: Union[Address, ChecksumAddress, str]


class ERC20Like:
    def __init__(self):
        self.key = None
        self.fernet = None
        self.web3 = None
        self.address = None
        self.router_address = None
        self.factory_address = None
        self.router_contract = None
        self.factory_contract = None

    async def set_router_contract(self):
        if not self.router_contract:
            self.router_contract = self.web3.eth.contract(
                address=self.router_address, abi=await self.get_contract_abi(abi_type="router")
            )

    async def set_factory_contract(self):
        if not self.factory_contract:
            self.factory_contract = self.web3.eth.contract(
                address=self.factory_address, abi=await self.get_contract_abi(abi_type="factory")
            )

    @staticmethod
    def get_decimal_representation(quantity: Wei, decimals: int) -> Decimal:
        """
        Decimal representation of inputted quantity
        Args:
            quantity (Wei): Amount to convert to decimal representation
            decimals (int): Amount of decimals for token contract

        Returns: Decimal/Normalized representation of inputted quantity
        """
        if decimals < 9:
            decimals += 2
        return quantity / Decimal(10 ** (18 - (decimals % 18)))

    @staticmethod
    async def get_contract_abi(abi_type: str = "liquidity") -> str:
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
        elif abi_type == "factory":
            filename = "abi/factory_erc20.abi"
        async with aiofiles.open(filename, mode='r') as file:
            data = await file.read()
            abi = json.loads(data)
        return abi

    def _swap_exact_eth_for_tokens(
            self, contract: Contract, route: list, amount_to_spend: Wei, gas_price: Wei
    ) -> TxParams:
        """
        Swaps exact ETH|BNB|MATIC for tokens.
        Args:
            contract (Contract): Token contract for swapping
            route (list): Token route to take for swap
            amount_to_spend (Wei): Amount to spend on swap
            gas_price (Wei): gas price to use

        Returns (TxParams): Transaction to be signed

        """
        logger.info("Swapping exact bnb for tokens")
        return contract.functions.swapExactETHForTokens(
            0, route, self.address, (int(time.time()) + 10000)
        ).buildTransaction(
            {
                "from": self.address,
                "value": amount_to_spend,
                "gasPrice": gas_price,
                "nonce": self.web3.eth.get_transaction_count(self.address),
            }
        )

    def _swap_exact_eth_for_tokens_supporting_fee_on_transfer_tokens(
            self, contract: Contract, route: list, amount_to_spend: Wei, gas_price: Wei
    ) -> TxParams:
        """
        Swaps exact ETH|BNB|MATIC for tokens supporting fee on transfer tokens
        Args:
            contract (Contract): Token contract for swapping
            route (list): Token route to take for swap
            amount_to_spend (Wei): Amount to spend on swap
            gas_price (Wei): gas price to use

        Returns (TxParams): Transaction to be signed

        """
        logger.info("Swapping exact bnb for tokens supporting fee on transfer tokens")
        return contract.functions.swapExactETHForTokensSupportingFeeOnTransferTokens(
            0, route, self.address, (int(time.time()) + 10000)
        ).buildTransaction(
            {
                "from": self.address,
                "value": amount_to_spend,
                "gasPrice": gas_price,
                "nonce": self.web3.eth.get_transaction_count(self.address),
            }
        )

    def _swap_exact_tokens_for_eth(
            self, contract: Contract, route: list, amount_to_spend: Wei, gas_price: Wei
    ) -> TxParams:
        """
        Swaps exact tokens for ETH|BNB|MATIC
        Args:
            contract (Contract): Token contract for swapping
            route (list): Token route to take for swap
            amount_to_spend (Wei): Amount to spend on swap
            gas_price (Wei): gas price to use

        Returns (TxParams): Transaction to be signed

        """
        logger.info("Swapping exact tokens for eth|bnb|matic")
        return contract.functions.swapExactTokensForETH(
            amount_to_spend,
            0,
            route,
            self.address,
            (int(time.time()) + 1000000),
        ).buildTransaction(
            {
                "from": self.address,
                "gasPrice": gas_price,
                "nonce": self.web3.eth.get_transaction_count(self.address),
            }
        )

    def _swap_exact_tokens_for_eth_supporting_fee_on_transfer_tokens(
            self, contract: Contract, route: list, amount_to_spend: Wei, gas_price: Wei
    ) -> TxParams:
        """
        Swaps exact tokens for ETH|BNB|MATIC supporting fee on transfer tokens
        Args:
            contract (Contract): Token contract for swapping
            route (list): Token route to take for swap
            amount_to_spend (Wei): Amount to spend on swap
            gas_price (Wei): gas price to use

        Returns (TxParams): Transaction to be signed

        """
        logger.info("Swapping exact tokens for bnb supporting fee on transfer tokens")
        return contract.functions.swapExactTokensForETHSupportingFeeOnTransferTokens(
            amount_to_spend,
            0,
            route,
            self.address,
            (int(time.time()) + 1000000),
        ).buildTransaction(
            {
                "from": self.address,
                "gasPrice": gas_price,
                "nonce": self.web3.eth.get_transaction_count(self.address),
            }
        )

    def _approve(self, contract: Contract) -> None:
        """
        Approves token for spending
        Args:
            contract (Contract): Token contract

        """
        logger.info("Approving token for swap")
        max_approval = int(
            "0x000000000000000fffffffffffffffffffffffffffffffffffffffffffffffff",
            16,
        )
        approve = contract.functions.approve(
            self.router_address, max_approval
        ).buildTransaction(
            {
                "from": self.address,
                "gasPrice": self.web3.toWei("5", "gwei"),
                "nonce": self.web3.eth.get_transaction_count(self.address),
            }
        )
        signed_txn = self.web3.eth.account.sign_transaction(
            approve,
            private_key=self.fernet.decrypt(self.key.encode()).decode(),
        )
        txn = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        self.web3.eth.wait_for_transaction_receipt(txn, timeout=6000)
        time.sleep(1)
        logger.info("Approved token for swap")

    async def _check_approval(
            self, contract: Contract, token: Union[Address, ChecksumAddress, str], balance: Wei = 0  # type: ignore
    ) -> None:
        """
        Validates token is approved for swapping. If not, approves token for swapping.
        Args:
            contract (Contract): Token Contract
            token (AddressLike): Token to check approval
            balance (Wei): Token balance

        """
        logger.info("Verifying token (%s) has approval", token)
        balance = (
            await self.get_token_balance(address=self.address, token=token)
            if balance == 0
            else balance
        )
        allowance = contract.functions.allowance(
            self.address, self.router_address
        ).call()

        if balance > allowance:
            self._approve(contract=contract)

    async def get_token_balance(self, address, token):
        raise NotImplementedError

    async def get_token(self, address: Union[Address, ChecksumAddress, str]) -> ERC20Token:
        """
        Retrieves metadata like its name, symbol, and decimals.
        Args:
            address (AddressLike): Contract address of a given token

        Returns: Token

        """
        logger.info("Retrieving metadata for token: %s", address)
        abi = await self.get_contract_abi(abi_type="sell")
        token_contract = self.web3.eth.contract(address=address, abi=abi)

        name = token_contract.functions.name().call()
        symbol = token_contract.functions.symbol().call()
        decimals = token_contract.functions.decimals().call()
        return ERC20Token(
            name=name, symbol=symbol, decimals=decimals, network="ETH", address=address
        )


class EthereumChain(ERC20Like):
    def __init__(self):
        super(EthereumChain, self).__init__()
        # TODO: Wait for async support
        self.web3 = Web3(
            Web3.HTTPProvider(ETHEREUM_MAIN_NET_URL, request_kwargs={"timeout": 60})
        )
        self.router_address = self.web3.toChecksumAddress(
            "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
        )

    async def get_account_token_holdings(
            self, address: Union[Address, ChecksumAddress, str] = None
    ) -> DataFrame:
        """
        Retrieves account holding for wallet address

        Returns (dict): User account holdings

        """
        if not address:
            address = self.address
        logger.info("Gathering account holdings for %s", address)
        account_holdings = []
        holdings = {
            "ETH": {
                "address": self.web3.toChecksumAddress(CONTRACT_ADDRESSES["ETH"]),
                "decimals": 18,
            }
        }
        async with aiohttp.ClientSession() as session:
            url = "https://api.etherscan.io/api"
            params = {'module': 'account', 'action': 'tokentx',
                      'address': self.address,
                      'startblock': 0, 'endblock': 99999999, 'sort': 'desc',
                      'apikey': ETHERSCAN_API_KEY}
            async with session.get(url, params=params) as response:
                data = await response.json()
                erc20_transfers = data['result']

        for transfer in erc20_transfers:
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
            quantity = await self.get_token_balance(address=address, token=token)

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
        if token == CONTRACT_ADDRESSES["ETH"]:
            return self.web3.eth.get_balance(address)

        abi = await self.get_contract_abi(abi_type="sell")
        contract = self.web3.eth.contract(address=token, abi=abi)
        return contract.functions.balanceOf(address).call()

    async def get_token_price(self, token, decimals):
        raise NotImplementedError


class UniSwap(EthereumChain):
    def __init__(self, address: str, key: str):
        super(UniSwap, self).__init__()
        self.address = self.web3.toChecksumAddress(address)
        self.key = key
        self.fernet = Fernet(FERNET_KEY)

    async def get_token_price(
            self, token: Union[Address, ChecksumAddress, str], decimals: int = 18
    ) -> Decimal:
        """
        Gets token price in USDC
        Args:
            token (AddressLike): Contract Address of coin
            decimals (int): Token decimals

        Returns (Decimal): Token price in USDC

        """
        logger.info("Retrieving token price in USDC for %s", token)
        usdc = CONTRACT_ADDRESSES["USDC"]
        eth = CONTRACT_ADDRESSES["ETH"]
        weth = CONTRACT_ADDRESSES["WETH"]
        route = [usdc, weth, token] if token not in (eth, weth) else [usdc, weth]
        qty = 10 ** decimals

        await self.set_router_contract()

        try:
            token_price = self.web3.fromWei(
                self.router_contract.functions.getAmountsIn(qty, route).call()[0],
                "mwei",
            )
        except ContractLogicError:
            token_price = 0
        return token_price

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
        await self.set_router_contract()

        if self.web3.isConnected():
            token = self.web3.toChecksumAddress(token)
            weth = CONTRACT_ADDRESSES["WETH"]
            gas_price = (
                await self.get_gas_price(speed=AVERAGE_TRANSACTION_SPEED)
                if not is_snipe
                else await self.get_gas_price(speed=FAST_TRANSACTION_SPEED)
            )
            try:
                txn = None
                abi = self.get_contract_abi(abi_type="router")
                token_abi = self.get_contract_abi(abi_type="sell")
                contract = self.web3.eth.contract(address=self.router_address, abi=abi)
                token_contract = self.web3.eth.contract(address=token, abi=token_abi)

                if side == BUY:
                    amount_to_spend = self.web3.toWei(amount_to_spend, "ether")
                    route = [weth, token]
                    args = (contract, route, amount_to_spend, gas_price)
                    swap_methods = [
                        self._swap_exact_eth_for_tokens,
                        self._swap_exact_eth_for_tokens_supporting_fee_on_transfer_tokens,
                    ]
                    balance = await self.get_token_balance(
                        address=self.address, token=CONTRACT_ADDRESSES["ETH"]
                    )
                else:
                    amount_to_spend = self.get_token_balance(
                        address=self.address, token=token  # type: ignore
                    )
                    route = [token, CONTRACT_ADDRESSES["WETH"]]
                    args = (contract, route, amount_to_spend, gas_price)
                    swap_methods = [
                        self._swap_exact_tokens_for_eth,
                        self._swap_exact_tokens_for_eth_supporting_fee_on_transfer_tokens,
                    ]
                    balance = await self.get_token_balance(address=self.address, token=token)  # type: ignore
                    await self._check_approval(
                        contract=token_contract,
                        token=token,  # type: ignore
                        balance=balance,
                    )

                if balance < amount_to_spend:
                    raise ValueError(f"Insufficient balance. Had {balance}, needed {amount_to_spend}")  # type: ignore

                for swap_method in swap_methods:
                    try:
                        txn = swap_method(*args)  # type: ignore
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
                txn_hash_url = f"https://etherscan.io/tx/{txn_hash}"
                reply = f"Transactions completed successfully. {link(title='View Transaction', url=txn_hash_url)}"

                # Pre-approve token for future swaps
                await self._check_approval(
                    contract=token_contract,
                    token=token,  # type: ignore
                    balance=self.get_token_balance(address=self.address, token=token),  # type: ignore
                )
            except ValueError as e:
                logger.exception(e)
                reply = str(e)
        else:
            logger.info("Unable to connect to Polygon Network")
            reply = "⚠ Sorry, I was unable to connect to the Ethereum Network. Try again later."
        return reply

    @staticmethod
    async def get_gas_price(speed: str):
        gas_prices = await gas_tracker.get_gasprices()
        return gas_prices[speed]
