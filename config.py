import os
from enum import Enum

from dotenv import load_dotenv
from pyngrok import ngrok


class RegisterTypes(Enum):
    BSC = "BSC"
    ETH = "ETH"
    MATIC = "MATIC"
    KUCOIN = "KUCOIN"
    COINBASE = "COINBASE"


load_dotenv()

# ENV settings
DEV = "dev"
PROD = "prod"
TEST = "test"
ENV = os.getenv("ENV", DEV).lower()
FERNET_KEY = os.getenv("FERNET_KEY").encode()  # type: ignore
REGISTER_TYPES = ("BSC", "KUCOIN")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 "
    "Safari/537.36 "
}
GREETINGS = [
    "Welcome fellow degen 😈 %s",
    "To the moon and beyond! %s",
    "Much wow, very new %s",
    "Stonk Army! %s",
]

# Binance Smart Chain settings
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY")
BUY = "BUY"
SELL = "SELL"
STOP = "STOP"

# Ethereum Main Net settings
ETHEREUM_MAIN_NET_URL = os.getenv("ETHEREUM_MAIN_NET_URL")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

# Polygon settings
POLYGONSCAN_API_KEY = os.getenv("POLYGONSCAN_API_KEY")

# Telegram env settings
TELEGRAM_BOT_API_KEY = os.getenv("TELEGRAM_BOT_API_KEY")

# NGROK Settings
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
ngrok.set_auth_token(NGROK_AUTH_TOKEN)

# Webhooks settings
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "localhost")
WEBAPP_PORT = os.getenv("WEBAPP_PORT", 8000)
WEBHOOK_PATH = f"/webhook/{TELEGRAM_BOT_API_KEY}"

https_tunnel = ngrok.connect(addr=WEBAPP_PORT, bind_tls=True)
WEBHOOK_URL = f"{https_tunnel.public_url}{WEBHOOK_PATH}"

# DB settings
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")
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
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))  # type: ignore
KUCOIN_TASK_NAME = "KUCOIN_BOT"

# CoinMarketCap settings
COIN_MARKET_CAP_API_KEY = os.getenv("COIN_MARKET_CAP_API_KEY")
