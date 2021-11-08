import asyncio
from decimal import Decimal

from copra.rest import Client
from cryptography.fernet import Fernet
from pandas import DataFrame

from app import logger
from config import FERNET_KEY


class CoinBaseApi:
    def __init__(self, api_key, api_secret, api_passphrase):
        self._fernet = Fernet(FERNET_KEY)
        self._api_key = self._fernet.decrypt(api_key.encode()).decode()
        self._api_secret = self._fernet.decrypt(api_secret.encode()).decode()
        self._api_passphrase = self._fernet.decrypt(api_passphrase.encode()).decode()
        self.coinbase_client = Client(
            loop=asyncio.get_event_loop(),
            auth=True,
            key=self._api_key,
            secret=self._api_secret,
            passphrase=self._api_passphrase,
        )

    async def get_account_token_holdings(self):
        logger.info("Gathering coinbase account holdings")
        account_holdings = []

        async with self.coinbase_client as client:
            accounts = await client.accounts()

            for account in accounts:
                balance = Decimal(account["balance"])

                if balance > 0:
                    symbol = account["currency"]
                    logger.info(
                        "Retrieving coinbase account ticker data for %s", symbol
                    )
                    exchange_rate = await client.ticker(product_id=f"{symbol}-USD")
                    price = Decimal(exchange_rate["price"])
                    holdings = {
                        "Symbol": account["currency"],
                        "Balance": balance,
                        "USD": (balance * price).quantize(Decimal("0.01")),
                    }
                    account_holdings.append(holdings)
        return DataFrame(account_holdings)
