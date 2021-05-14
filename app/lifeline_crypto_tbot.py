import asyncio

from aiogram import Dispatcher, executor

from app import DEV, ENV, PORT, WEBAPP_HOST, WEBHOOK_PATH, WEBHOOK_URL, bot, dp
from handler.base import send_greeting, send_welcome
from handler.bot.kucoin_bot import kucoin_bot
from handler.crypto import (send_coin, send_coin_address, send_gas,
                            send_latest_listings, send_price_alert,
                            send_trending)
from handler.error import send_error


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
