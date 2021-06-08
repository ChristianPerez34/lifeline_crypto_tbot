from coinmarketcapapi import CoinMarketCapAPI

from config import COIN_MARKET_CAP_API_KEY
from handlers import logger


class CoinMarketCap:
    def __init__(self):
        self.cmc = CoinMarketCapAPI(COIN_MARKET_CAP_API_KEY)

    def coin_lookup(self, symbol: str) -> dict:
        """Coin lookup in CoinMarketCap API

        Args:
            symbol (str): Symbol of coin to lookup

        Returns:
            dict: Results of coin lookup
        """
        logger.info(f"Looking up price for {symbol} in CoinMarketCap API")
        return self.cmc.cryptocurrency_quotes_latest(symbol=symbol, convert="usd").data[
            symbol
        ]
