from decimal import Decimal

from web3 import Web3


class BinanceSmartChain:
    def __init__(self):
        self.web3 = Web3(Web3.HTTPProvider(
            'https://bsc-dataseed.binance.org/'))

    def get_account_balance(self, address: str) -> Decimal:
        return self.web3.fromWei(self.web3.eth.get_balance(address), 'ether')
