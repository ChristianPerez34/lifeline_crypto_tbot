import os

from dotenv import load_dotenv

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
