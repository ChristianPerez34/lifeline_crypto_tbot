import aiohttp
import pandas as pd
from coinmarketcapapi import CoinMarketCapAPI

from app import logger
from config import COIN_MARKET_CAP_API_KEY, HEADERS


class CoinMarketCap:
    def __init__(self):
        self.cmc = CoinMarketCapAPI(COIN_MARKET_CAP_API_KEY)

    def get_coin_ids(self, symbol: str) -> list:
        """
        Retrieves coin ids for matching symbol
        Args:
            symbol (str): Token symbol

        Returns (list): List of token ids

        """
        logger.info("Looking up token ids for %s in CoinMarketCap API", symbol)
        return [
            (str(item["id"]), item["name"])
            for item in self.cmc.cryptocurrency_map(symbol=symbol).data
        ]

    def get_coin_metadata(self, ids: str) -> dict:
        """
        Retrieves coin metadata
        Args:
            ids (str): Token id

        Returns (list): Metadata for provided coin ids

        """
        return self.cmc.cryptocurrency_info(id=ids).data

    def coin_lookup(self, ids: str) -> dict:
        """Coin lookup in CoinMarketCap API

        Args:
            ids (str): CoinMarketCap token ids

        Returns:
            dict: Results of coin lookup
        """
        logger.info("Looking up price for %s in CoinMarketCap API", ids)
        return self.cmc.cryptocurrency_quotes_latest(id=ids, convert="usd").data

    @staticmethod
    async def get_trending_coins() -> list:
        """
        Scalps trending coins from CoinMarketCap website
        Returns (list): Trending coins

        """
        logger.info("Retrieving trending coins from CoinMarketCap")
        coins = []
        async with aiohttp.ClientSession() as session, session.get(
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
