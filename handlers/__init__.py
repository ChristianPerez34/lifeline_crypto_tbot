from aioetherscan import Client
from ethereum_gasprice import AsyncGaspriceController
from ethereum_gasprice.providers import EtherscanProvider
from lru import LRU

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_USER, ETHERSCAN_API_KEY

# Enable logging
from models import db

coingecko_coin_lookup_cache = LRU(5)

ether_scan = Client(ETHERSCAN_API_KEY)
gas_tracker = AsyncGaspriceController(
    settings={EtherscanProvider.title: ETHERSCAN_API_KEY},
)


async def init_database():
    db.bind(
        provider="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        database=DB_NAME,
    )
    db.generate_mapping(create_tables=True)
