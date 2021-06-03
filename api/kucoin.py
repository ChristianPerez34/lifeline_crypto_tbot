from decimal import Decimal

from kucoin_futures.client import Market, Trade, User


class KucoinApi:
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str):
        self.trade_client = Trade(
            key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False
        )
        self.user_client = User(
            key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False
        )
        self.market_client = Market(
            key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False
        )

    def get_balance(self) -> Decimal:
        """
        Retrieves available balance on futures account
        Returns: balance

        """
        account_overview = self.user_client.get_account_overview(currency="USDT")
        return Decimal(account_overview["availableBalance"])

    def create_market_order(self, symbol: str, side: str, size: int, lever: str = "10"):
        return self.trade_client.create_market_order(
            symbol=symbol,
            side="buy" if side == "LONG" else "sell",
            lever=lever,
            size=size,
        )

    def get_open_stop_order(self) -> list:
        """
        Retrieves open stop orders on futures account
        Returns: List of open stop orders

        """
        return self.trade_client.get_open_stop_order()["items"]

    def get_all_position(self) -> list:
        """
        Retrieves all open futures positions on futures account
        Returns: List of all positions

        """
        positions = self.trade_client.get_all_position()
        return positions if isinstance(positions, list) else []

    def get_ticker(self, symbol) -> dict:
        """
        Gets real-time market data for symbol
        Args:
            symbol (str): Crypto symbol to get data for

        Returns: Real time crypto symbol data

        """
        return self.market_client.get_ticker(symbol=symbol)
