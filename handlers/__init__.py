import os

from etherscan import Etherscan
from lru import LRU

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_USER

# Enable logging
from models import db

coingecko_coin_lookup_cache = LRU(5)

eth = Etherscan(os.getenv("ETHERSCAN_API_KEY"))


async def init_database():
    db.bind(
        provider="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        database=DB_NAME,
    )
    db.generate_mapping(create_tables=True)
