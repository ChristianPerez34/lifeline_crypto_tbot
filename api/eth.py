import json
import time
from decimal import Decimal
from typing import Union

from aiogram.utils.markdown import link
from cryptography.fernet import Fernet
from uniswap import Uniswap
from uniswap.exceptions import InsufficientBalance
from uniswap.types import AddressLike
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError
from web3.types import Wei, TxParams

from app import logger
from config import FERNET_KEY, ETHEREUM_MAIN_NET_URL, BUY
from handlers import ether_scan

CONTRACT_ADDRESSES = {
    "ETH": Web3.toChecksumAddress("0x0000000000000000000000000000000000000000"),
    "WETH": Web3.toChecksumAddress("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    "USDC": Web3.toChecksumAddress("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"),
}

AVERAGE_TRANSACTION_SPEED = "ProposeGasPrice"
FAST_TRANSACTION_SPEED = "FastGasPrice"


class ERC20Like:
    def __init__(self):
        self.key = None
        self.fernet = None
        self.dex = None
        self.web3 = None
        self.address = None

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
            self.dex.router_address, max_approval
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
        self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        logger.info("Approved token for swap")
        time.sleep(10)

    def _check_approval(
        self, contract: Contract, token: AddressLike, balance: Wei
    ) -> None:
        """
        Validates token is approved for swapping. If not, approves token for swapping.
        Args:
            contract (Contract): Token Contract
            token (AddressLike): Token to check approval
            balance (Wei): Token balance

        """
        logger.info("Verifying token (%s) has approval", token)
        allowance = contract.functions.allowance(token, self.dex.router_address).call()

        if balance > allowance:
            self._approve(contract=contract)

    def get_token_balance(self, address, token):
        raise NotImplementedError


class EthereumChain(ERC20Like):
    def __init__(self):
        super(EthereumChain, self).__init__()
        self.web3 = Web3(
            Web3.HTTPProvider(ETHEREUM_MAIN_NET_URL, request_kwargs={"timeout": 60})
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
            "ETH": {
                "address": self.web3.toChecksumAddress(CONTRACT_ADDRESSES["ETH"]),
                "decimals": 18,
            }
        }

        erc20_transfers = ether_scan.get_erc20_token_transfer_events_by_address(
            address=address, startblock=0, endblock=99999999, sort="desc"
        )

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
            weth = CONTRACT_ADDRESSES["WETH"]
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
                    route = [weth, token]
                    args = (contract, route, amount_to_spend, gas_price)
                    swap_methods = [
                        self._swap_exact_eth_for_tokens,
                        self._swap_exact_eth_for_tokens_supporting_fee_on_transfer_tokens,
                    ]
                    balance = self.get_token_balance(
                        address=self.address, token=CONTRACT_ADDRESSES["ETH"]
                    )
                else:
                    token_abi = self.get_contract_abi(abi_type="sell")
                    token_contract = self.web3.eth.contract(
                        address=token, abi=token_abi
                    )
                    amount_to_spend = self.get_token_balance(
                        address=self.address, token=token
                    )
                    route = [token, CONTRACT_ADDRESSES["WETH"]]
                    args = (contract, route, amount_to_spend, gas_price)
                    swap_methods = [
                        self._swap_exact_tokens_for_eth,
                        self._swap_exact_tokens_for_eth_supporting_fee_on_transfer_tokens,
                    ]
                    balance = self.get_token_balance(address=self.address, token=token)
                    self._check_approval(
                        contract=token_contract, token=token, balance=balance
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
                txn_hash_url = f"https://etherscan.io/tx/{txn_hash}"
                reply = f"Transactions completed successfully. {link(title='View Transaction', url=txn_hash_url)}"
            except InsufficientBalance as e:
                logger.exception(e)
                reply = (
                    "⚠️ Insufficient balance. Top up your token balance and try again. "
                )
            except ValueError as e:
                logger.exception(e)
                reply = str(e)
        else:
            logger.info("Unable to connect to Polygon Network")
            reply = "⚠ Sorry, I was unable to connect to the Ethereum Network. Try again later."
        return reply

    @staticmethod
    def get_gas_price(speed: str):
        return ether_scan.get_gas_oracle()[speed]
