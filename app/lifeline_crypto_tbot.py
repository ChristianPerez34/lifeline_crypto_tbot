import asyncio

from aiogram import Dispatcher, types
from aiogram import executor

from app import dp
from config import KUCOIN_TASK_NAME
from handlers import init_database
from handlers.base import send_greeting
from handlers.base import send_welcome
from handlers.crypto import kucoin_inline_query_handler, send_sell_coin, send_spy
from handlers.crypto import price_alert_callback
from handlers.crypto import send_balance
from handlers.crypto import send_buy_coin
from handlers.crypto import send_candle_chart
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
from models import CryptoAlert


async def on_startup(dispatcher: Dispatcher):
    """Bot startup actions

    Args:
        dispatcher (Dispatcher): Bot dispatcher
    """
    await init_database()
    for alert in await CryptoAlert.all():
        asyncio.create_task(price_alert_callback(alert=alert, delay=15))

    setup_handlers(dispatcher)


async def on_shutdown(_):
    """Disable KuCoin bot on shutdown"""
    tasks = asyncio.all_tasks()

    for task in tasks:
        if task.get_name() == KUCOIN_TASK_NAME:
            task.cancel()


def setup_handlers(dispatcher: Dispatcher) -> None:
    """Registers handlers

    Args:
        dispatcher (Dispatcher): Bot dispatcher
    """
    dispatcher.register_message_handler(send_welcome,
                                        commands=["start", "help"])
    dispatcher.register_message_handler(send_coin, commands=["coin"])
    dispatcher.register_message_handler(send_gas, commands=["gas"])
    dispatcher.register_message_handler(send_coin_address,
                                        commands=["coin_address"])
    dispatcher.register_message_handler(send_trending, commands=["trending"])
    dispatcher.register_message_handler(send_chart, commands=["chart"])
    dispatcher.register_message_handler(send_candle_chart, commands=["candle"])
    dispatcher.register_message_handler(send_price_alert, commands=["alert"])
    dispatcher.register_message_handler(send_latest_listings,
                                        commands=["latest_listings"])
    dispatcher.register_message_handler(send_restart_kucoin_bot,
                                        commands=["restart_kucoin"])
    dispatcher.register_message_handler(send_buy_coin, commands=["buy_coin"])
    dispatcher.register_message_handler(send_register, commands=["register"])
    dispatcher.register_message_handler(send_balance, commands=["balance"])
    dispatcher.register_callback_query_handler(kucoin_inline_query_handler)
    dp.register_message_handler(send_sell_coin, commands=["sell_coin"])
    dp.register_message_handler(send_spy, commands=['spy'])
    dispatcher.register_message_handler(
        send_greeting, content_types=types.ContentTypes.NEW_CHAT_MEMBERS)
    dispatcher.register_errors_handler(send_error)


if __name__ == "__main__":
    executor.start_polling(dp,
                           skip_updates=True,
                           on_startup=on_startup,
                           on_shutdown=on_shutdown)
