import logging
import os

from coinmarketcapapi import CoinMarketCapAPI
from etherscan import Etherscan
from lru import LRU
from pycoingecko import CoinGeckoAPI

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)
crypto_cache = LRU(5)
cmc = CoinMarketCapAPI(os.getenv("COIN_MARKET_CAP_API_KEY"))
cg = CoinGeckoAPI()
eth = Etherscan(os.getenv("ETHERSCAN_API_KEY"))
