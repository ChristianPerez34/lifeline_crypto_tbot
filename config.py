import os
from enum import Enum

from dotenv import load_dotenv


class RegisterTypes(Enum):
    BSC = "BSC"
    KUCOIN = "KUCOIN"


load_dotenv()

# ENV settings
DEV = "dev"
PROD = "prod"
TEST = "test"
ENV = os.getenv("ENV", DEV).lower()
FERNET_KEY = os.getenv("FERNET_KEY")
REGISTER_TYPES = ("BSC", "KUCOIN")

# Binance Smart Chain settings
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
BUY = "BUY"
SELL = "SELL"

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
            "models": ["models", "aerich.models"],
            "default_connection": "default",
        }
    },
}

# KuCoin settings
KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
KUCOIN_API_SECRET = os.getenv("KUCOIN_API_SECRET")
KUCOIN_API_PASSPHRASE = os.getenv("KUCOIN_API_PASSPHRASE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
KUCOIN_TASK_NAME = "KUCOIN_BOT"

# CoinMarketCap settings
COIN_MARKET_CAP_API_KEY = os.getenv("COIN_MARKET_CAP_API_KEY")
