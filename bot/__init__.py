import os

KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
KUCOIN_API_SECRET = os.getenv("KUCOIN_API_SECRET")
KUCOIN_API_PASSPHRASE = os.getenv("KUCOIN_API_PASSPHRASE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
KUCOIN_TASK_NAME = "KUCOIN_BOT"

active_orders = {}