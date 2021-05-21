import os

from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

# ENV settings
DEV = "dev"
PROD = "prod"
TEST = "test"
ENV = os.getenv("ENV", DEV).lower()
FERNET_KEY = os.getenv("FERNET_KEY")

# Binance Smart Chain settings
BINANCE_SMART_CHAIN_URL = "https://bsc-dataseed.binance.org/"
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
BSCSCAN_API_URL = "https://api.bscscan.com/api?module=contract&action=getabi&address={address}&apikey={api_key}"
PANCAKESWAP_FACTORY_ADDRESS = Web3.toChecksumAddress("0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73")
PANCAKESWAP_ROUTER_ADDRESS = Web3.toChecksumAddress("0x10ED43C718714eb63d5aA57B78B54704E256024E")
BNB_ADDRESS = "0x0000000000000000000000000000000000000000"
MAX_SLIPPAGE = 0.1
BUY = 'BUY'
SELL = 'SELL'
GAS = 250000
GAS_PRICE = Web3.toWei("10", "gwei")

# Telegram env settings
TELEGRAM_BOT_API_KEY = os.getenv("TELEGRAM_BOT_API_KEY")

# Webhooks settings
WEBHOOK_HOST = os.getenv("HEROKU_APP_URL")
WEBHOOK_PATH = f"/webhook/{TELEGRAM_BOT_API_KEY}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# webserver settings
WEBAPP_HOST = "0.0.0.0"  # or ip
WEBAPP_PORT = os.getenv("PORT", 8443)

# DB settings
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)
DB_URL = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DB_CONFIG = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.asyncpg",
            "credentials": {
                "database": DB_NAME,
                "host": DB_HOST,
                "password": DB_PASSWORD,
                "port": DB_PORT,
                "user": DB_USER,
            },
        }
    },
    "apps": {
        "models": {
            "models": ["models"],
            "default_connection": "default",
        }
    },
}
