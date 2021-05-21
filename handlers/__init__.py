import logging
import os

from coinmarketcapapi import CoinMarketCapAPI
from etherscan import Etherscan
from lru import LRU
from pycoingecko import CoinGeckoAPI
from tortoise import Tortoise

from config import DB_CONFIG

# Enable logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)
coingecko_coin_lookup_cache = LRU(5)
cmc = CoinMarketCapAPI(os.getenv("COIN_MARKET_CAP_API_KEY"))
cg = CoinGeckoAPI()
eth = Etherscan(os.getenv("ETHERSCAN_API_KEY"))


async def init_database():
    await Tortoise.init(modules={"models": ["models"]}, config=DB_CONFIG)
    # Generate the schema
    await Tortoise.generate_schemas()
