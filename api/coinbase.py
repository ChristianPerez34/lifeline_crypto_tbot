import asyncio
from decimal import Decimal

from copra.rest import Client
from cryptography.fernet import Fernet
from pandas import DataFrame

from app import logger
from config import FERNET_KEY, BUY, SELL


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

    async def trade(self, order_type: str, trade_direction: str, symbol: str, amount: float,
                    limit_price: float = None):
        async with self.coinbase_client as client:
            accounts = [account for account in await client.accounts() if account['currency'] == symbol]
            available_balance = float(accounts[0]['available'])

            product_id = f"{symbol}-USD"

            if order_type == "market":
                amount = amount if trade_direction == BUY.lower() else available_balance
                funds = amount
                size = None

                if trade_direction == SELL.lower():
                    funds = None
                    size = amount
                response = await client.market_order(side=trade_direction, product_id=product_id,
                                                     size=size, funds=funds)
            else:
                if not limit_price:
                    raise ValueError("Limit orders must have 'limit_price' parameter set")
                num_decimals = len([product for product in await client.products() if product['id'] == product_id][0][
                                       'base_increment'].split('.')[1])

                exchange_rate = await client.ticker(product_id=product_id)
                size = round(float(amount / float(exchange_rate["price"])), num_decimals)
                price = limit_price

                if trade_direction == BUY.lower():
                    response = await client.limit_order(side=trade_direction, product_id=product_id, size=size,
                                                        price=price)
                elif trade_direction == SELL.lower():
                    # Sell all available funds if calculated size is greater than available balance
                    size = size if size < available_balance else available_balance
                    response = await client.limit_order(side=trade_direction, product_id=product_id, size=size,
                                                        price=price)
                else:
                    # Limit stop loss
                    stop_price = limit_price
                    response = await client.limit_order(side=SELL.lower(), product_id=product_id,
                                                        size=size, stop="loss", price=price,
                                                        stop_price=stop_price)

            return response
