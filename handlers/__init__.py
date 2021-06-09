import logging
import os
from pathlib import Path

from etherscan import Etherscan
from lru import LRU
from tortoise import Tortoise

from config import DB_CONFIG

# Enable logging
log_file = str(Path.home().joinpath('logs/lifeline_crypto_tbot.log'))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(log_file, mode='w+'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
coingecko_coin_lookup_cache = LRU(5)

eth = Etherscan(os.getenv("ETHERSCAN_API_KEY"))


async def init_database():
    await Tortoise.init(modules={"models": ["models"]}, config=DB_CONFIG)
    # Generate the schema
    await Tortoise.generate_schemas()
