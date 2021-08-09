import asyncio

from aiogram import Dispatcher, executor, types

from app import dp
from bot.bsc_order import limit_order_executor
from config import KUCOIN_TASK_NAME, TELEGRAM_CHAT_ID
from handlers import init_database
from handlers.base import send_greeting, send_message, send_welcome
from handlers.crypto import (
    kucoin_inline_query_handler,
    price_alert_callback,
    send_balance,
    send_buy_coin,
    send_candle_chart,
    send_chart,
    send_gas,
    send_latest_listings,
    send_price,
    send_price_address,
    send_price_alert,
    send_restart_kucoin_bot,
    send_sell_coin,
    send_snipe,
    send_spy,
    send_trending, send_limit_swap,
)
from handlers.error import send_error
from handlers.user import send_register
from models import CryptoAlert, Order
from schemas import LimitOrder


async def on_startup(dispatcher: Dispatcher):
    """Bot startup actions

    Args:
        dispatcher (Dispatcher): Bot dispatcher
    """
    await init_database()

    for alert in CryptoAlert.all():
        asyncio.create_task(price_alert_callback(alert=alert, delay=15))
    for order in Order.all():
        limit_order = LimitOrder.from_orm(order)
        asyncio.create_task(limit_order_executor(order=limit_order))
    setup_handlers(dispatcher)

    await send_message(channel_id=TELEGRAM_CHAT_ID, message="Up and running! 👾")


async def on_shutdown(_):
    """Disable KuCoin bot on shutdown"""
    tasks = asyncio.all_tasks()

    await send_message(
        channel_id=TELEGRAM_CHAT_ID, message="Going offline! Be right back."
    )

    for task in tasks:
        if task.get_name() == KUCOIN_TASK_NAME:
            task.cancel()


def setup_handlers(dispatcher: Dispatcher) -> None:
    """Registers handlers

    Args:
        dispatcher (Dispatcher): Bot dispatcher
    """
    dispatcher.register_message_handler(send_welcome, commands=["start", "help"])
    dispatcher.register_message_handler(send_price, commands=["price"])
    dispatcher.register_message_handler(send_gas, commands=["gas"])
    dispatcher.register_message_handler(send_price_address, commands=["price_address"])
    dispatcher.register_message_handler(send_trending, commands=["trending"])
    dispatcher.register_message_handler(send_chart, commands=["chart"])
    dispatcher.register_message_handler(send_candle_chart, commands=["candle"])
    dispatcher.register_message_handler(send_price_alert, commands=["alert"])
    dispatcher.register_message_handler(
        send_latest_listings, commands=["latest_listings"]
    )
    dispatcher.register_message_handler(
        send_restart_kucoin_bot, commands=["restart_kucoin"]
    )
    dispatcher.register_message_handler(send_buy_coin, commands=["buy_coin"])
    dispatcher.register_message_handler(send_register, commands=["register"])
    dispatcher.register_message_handler(send_balance, commands=["balance"])
    dispatcher.register_callback_query_handler(kucoin_inline_query_handler)
    dispatcher.register_message_handler(send_sell_coin, commands=["sell_coin"])
    dispatcher.register_message_handler(send_spy, commands=["spy"])
    dispatcher.register_message_handler(send_snipe, commands=["snipe"])
    dispatcher.register_message_handler(send_limit_swap, commands=['limit'])

    dispatcher.register_message_handler(
        send_greeting, content_types=types.ContentTypes.NEW_CHAT_MEMBERS
    )
    dispatcher.register_errors_handler(send_error)


if __name__ == "__main__":
    import os

    print(os.getcwd())
    executor.start_polling(
        dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown
    )
