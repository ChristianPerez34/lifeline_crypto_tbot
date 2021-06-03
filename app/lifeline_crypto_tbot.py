import asyncio

from aiogram import Dispatcher
from aiogram import executor

from app import dp
from config import KUCOIN_TASK_NAME
from handlers import init_database
from handlers.base import send_greeting
from handlers.base import send_welcome
from handlers.crypto import kucoin_inline_query_handler
from handlers.crypto import send_buy_coin
from handlers.crypto import send_candlechart
from handlers.crypto import send_chart
from handlers.crypto import send_coin
from handlers.crypto import send_coin_address
from handlers.crypto import send_gas
from handlers.crypto import send_latest_listings
from handlers.crypto import send_price_alert
from handlers.crypto import send_restart_kucoin_bot
from handlers.crypto import send_trending
from handlers.error import send_error
from handlers.user import send_register


async def on_startup(dp: Dispatcher):
    """Bot stratup actions

    Args:
        dp (Dispatcher): Bot dispatcher
    """
    # if ENV != DEV:
    #     await bot.delete_webhook()
    #     await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    await init_database()
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
    dp.register_message_handler(send_chart, commands=["chart"])
    dp.register_message_handler(send_candlechart, commands=["candle"])
    dp.register_message_handler(send_price_alert, commands=["alert"])
    dp.register_message_handler(send_latest_listings,
                                commands=["latest_listings"])
    dp.register_message_handler(send_restart_kucoin_bot,
                                commands=["restart_kucoin"])
    dp.register_message_handler(send_buy_coin, commands=["buy_coin"])
    dp.register_message_handler(send_register, commands=["register"])
    dp.register_callback_query_handler(kucoin_inline_query_handler)
    # dp.register_message_handler(send_sell_coin, commands=["sell_coin"])
    dp.register_message_handler(send_greeting)
    dp.register_errors_handler(send_error),


if __name__ == "__main__":
    # if ENV == DEV:
    executor.start_polling(dp,
                           skip_updates=True,
                           on_startup=on_startup,
                           on_shutdown=on_shutdown)
    # else:
    #     executor.start_webhook(
    #         dispatcher=dp,
    #         webhook_path=WEBHOOK_PATH,
    #         on_startup=on_startup,
    #         on_shutdown=on_shutdown,
    #         skip_updates=True,
    #         host=WEBAPP_HOST,
    #         port=WEBAPP_PORT,
    #     )
