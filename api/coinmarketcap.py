import aiohttp
import pandas as pd
from coinmarketcapapi import CoinMarketCapAPI

from config import COIN_MARKET_CAP_API_KEY
from config import HEADERS
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

    @staticmethod
    async def get_trending_coins() -> list:
        """
        Scalps trending coins from CoinMarketCap website
        Returns (list): Trending coins

        """
        logger.info("Retrieving trending coins from CoinMarketCap")
        coins = []
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://coinmarketcap.com/trending-cryptocurrencies/", headers=HEADERS
            ) as response:
                df = pd.read_html(await response.text(), flavor="bs4")[0]

                for row in df.itertuples():
                    if row.Index > 6:
                        break
                    name = row.Name.replace(f"{row.Index + 1}", " ")
                    words = name.split()
                    words[-1] = f"({words[-1]})"
                    coin = " ".join(words)
                    coins.append(coin)
        return coins
