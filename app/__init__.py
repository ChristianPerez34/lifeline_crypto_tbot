import os

from aiogram import Bot
from aiogram import Dispatcher
from dotenv import load_dotenv

load_dotenv()

DEV = "dev"
PROD = "prod"
TEST = "test"
TELEGRAM_BOT_API_KEY = os.getenv("TELEGRAM_BOT_API_KEY")
ENV = os.getenv("ENV", DEV).lower()
WEBHOOK_HOST = os.getenv("HEROKU_APP_URL")
WEBHOOK_PATH = f"/{TELEGRAM_BOT_API_KEY}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
# webserver settings
WEBAPP_HOST = "localhost"  # or ip
WEBAPP_PORT = 8443

bot = Bot(token=TELEGRAM_BOT_API_KEY)
dp = Dispatcher(bot)
