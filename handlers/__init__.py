import logging
import os
from pathlib import Path

from etherscan import Etherscan
from lru import LRU

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_USER

# Enable logging
from models import db

log_file = str(Path.home().joinpath("logs/lifeline_crypto_tbot.log"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler(log_file, mode="w+"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)
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
