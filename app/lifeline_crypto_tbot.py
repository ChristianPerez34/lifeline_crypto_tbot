import asyncio

from aiogram import Dispatcher
from aiogram import executor

from app import bot
from app import DEV
from app import dp
from app import ENV
from app import PORT
from app import WEBAPP_HOST
from app import WEBHOOK_PATH
from app import WEBHOOK_URL
from bot import KUCOIN_TASK_NAME
from handler.base import send_greeting
from handler.base import send_welcome
from handler.crypto import send_coin
from handler.crypto import send_coin_address
from handler.crypto import send_gas
from handler.crypto import send_latest_listings
from handler.crypto import send_price_alert
from handler.crypto import send_restart_kucoin_bot
from handler.crypto import send_trending
from handler.error import send_error


async def on_startup(dp: Dispatcher):
    """Bot stratup actions

    Args:
        dp (Dispatcher): Bot dispatcher
    """
    if ENV != DEV:
        await bot.delete_webhook()
        await bot.set_webhook(WEBHOOK_URL)
    setup_handlers(dp)


async def on_shutdown(dp: Dispatcher):
    """Disable KuCoin bot on shutdown

    Args:
        dp (Dispatcher): Bot dispatcher
    """
    tasks = asyncio.all_tasks()
    [task.cancel() for task in tasks if task.get_name() == KUCOIN_TASK_NAME]


def setup_handlers(dp: Dispatcher) -> None:
    """Registers handlers

    Args:
        dp (Dispatcher): Bot dispatcher
    """
    dp.register_message_handler(send_welcome, commands=["start", "help"])
    dp.register_message_handler(send_coin, commands=["coin"])
    dp.register_message_handler(send_gas, commands=["gas"])
    dp.register_message_handler(send_coin_address, commands=["coin_address"])
    dp.register_message_handler(send_trending, commands=["trending"])
    dp.register_message_handler(send_price_alert, commands=["alert"])
    dp.register_message_handler(send_latest_listings,
                                commands=["latest_listings"])
    dp.register_message_handler(send_restart_kucoin_bot,
                                commands=["restart_kucoin"])
    dp.register_message_handler(send_greeting)
    dp.register_errors_handler(send_error),


if __name__ == "__main__":
    if ENV == DEV:
        executor.start_polling(dp,
                               skip_updates=True,
                               on_startup=on_startup,
                               on_shutdown=on_shutdown)
    else:
        executor.start_webhook(
            dispatcher=dp,
            webhook_path=WEBHOOK_PATH,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            skip_updates=True,
            host=WEBAPP_HOST,
            port=PORT,
        )
