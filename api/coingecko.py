from pycoingecko import CoinGeckoAPI

from handlers import logger, coingecko_coin_lookup_cache


class CoinGecko:
    def __init__(self):
        self.cg = CoinGeckoAPI()

    def coin_lookup(self, ids: str, is_address: bool = False) -> dict:
        """Coin lookup in CoinGecko API

            Args:
                ids (str): id of coin to lookup
                is_address (bool): Indicates if given ids is a crypto address

            Returns:
                dict: Data from CoinGecko API
            """
        logger.info(f"Looking up price for {ids} in CoinGecko API")
        try:
            data = (self.cg.get_coin_info_from_contract_address_by_id(
                id="ethereum", contract_address=ids)
                if is_address else self.cg.get_coin_by_id(id=ids))
        except Exception:
            data = (self.cg.get_coin_info_from_contract_address_by_id(
                id="binance", contract_address=ids)
                if is_address else self.cg.get_coin_by_id(id=ids))
        return data

    def get_trending_coins(self) -> list:
        """
        Gets trending coins
        Returns: Trending coins

        """
        logger.info("Retrieving CoinGecko trending coins")
        return self.cg.get_search_trending()["coins"]

    def coin_market_lookup(self, ids: str, time_frame: int, base_coin: str) -> dict:
        """Coin lookup in CoinGecko API for Market Chart

            Args:
                ids (str): id of coin to lookup
                time_frame (int): Indicates number of days for data span
                base_coin (str): Indicates base coin

            Returns:
                dict: Data from CoinGecko API
            """
        logger.info(f"Looking up chart data for {ids} in CoinGecko API")

        return self.cg.get_coin_market_chart_by_id(ids, base_coin, time_frame)

    def get_coin_id(self, symbol: str) -> str:
        """Retrieves coinstats from connected services crypto services

            Args:
                symbol (str): Cryptocurrency symbol of coin to lookup

            Returns:
                str: coin id of the cryptocurrency
            """
        logger.info(f"Getting coin ID for {symbol}")

        if symbol in coingecko_coin_lookup_cache.keys():
            coin_id = coingecko_coin_lookup_cache[symbol]

        else:
            coin = [
                coin for coin in self.cg.get_coins_list()
                if coin["symbol"].upper() == symbol
            ][0]
            coin_id = coin["id"]
            coingecko_coin_lookup_cache[symbol] = coin_id

        return coin_id
