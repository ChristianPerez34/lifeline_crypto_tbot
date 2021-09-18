import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.utils.callback_data import CallbackData

from config import TELEGRAM_BOT_API_KEY

log_file = str(Path.home().joinpath("logs/lifeline_crypto_tbot.log"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler(log_file, mode="w+"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_API_KEY)
dp = Dispatcher(bot)
chart_cb = CallbackData(
    "chart", "chart_type", "coin_id", "symbol", "time_frame", "base_coin"
)
