from aiogram import Bot, Dispatcher

from config import TELEGRAM_BOT_API_KEY

bot = Bot(token=TELEGRAM_BOT_API_KEY)
dp = Dispatcher(bot)
