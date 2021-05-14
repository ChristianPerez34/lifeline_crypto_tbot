import asyncio

from aiogram import Dispatcher
from aiogram import executor

from app import PORT, WEBAPP_HOST, bot
from app import DEV
from app import dp
from app import ENV
from app import WEBHOOK_PATH
from app import WEBHOOK_URL
from handler.error import send_error
from handler.base import send_greeting
from handler.base import send_welcome
from handler.bot.kucoin_bot import kucoin_bot
from handler.crypto import send_coin
from handler.crypto import send_coin_address
from handler.crypto import send_gas
from handler.crypto import send_latest_listings
from handler.crypto import send_price_alert
from handler.crypto import send_trending


async def on_startup(dp: Dispatcher):
    if ENV != DEV:
        await bot.delete_webhook()
        await bot.set_webhook(WEBHOOK_URL)
    setup_handlers(dp)
    asyncio.create_task(kucoin_bot())


def setup_handlers(dp: Dispatcher):
    dp.register_message_handler(send_welcome, commands=["start", "help"])
    dp.register_message_handler(send_coin, commands=["coin"])
    dp.register_message_handler(send_gas, commands=["gas"])
    dp.register_message_handler(send_coin_address, commands=["coin_address"])
    dp.register_message_handler(send_trending, commands=["trending"])
    dp.register_message_handler(send_price_alert, commands=["alert"])
    dp.register_message_handler(send_latest_listings, commands=["latest_listings"])
    dp.register_message_handler(send_greeting)
    dp.register_errors_handler(send_error),


if __name__ == "__main__":
    if ENV == DEV:
        executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    else:
        executor.start_webhook(
            dispatcher=dp,
            webhook_path=WEBHOOK_PATH,
            on_startup=on_startup,
            skip_updates=True,
            host=WEBAPP_HOST,
            port=PORT,
        )
