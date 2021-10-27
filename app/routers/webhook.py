import asyncio

from aiogram import types, Dispatcher, Bot
from fastapi import APIRouter
from pyngrok import ngrok

from app import dp, bot, chart_cb, alert_cb, price_cb
from bot.bsc_order import limit_order_executor
from config import NGROK_AUTH_TOKEN, TELEGRAM_CHAT_ID, WEBHOOK_PATH
from handlers import init_database
from handlers.base import send_welcome, send_greeting, send_message
from handlers.crypto import (
    send_price,
    send_gas,
    send_price_address,
    send_trending,
    send_chart,
    send_candle_chart,
    send_price_alert,
    send_latest_listings,
    send_restart_kucoin_bot,
    send_buy,
    send_balance,
    chart_inline_query_handler,
    kucoin_inline_query_handler,
    send_sell,
    send_spy,
    send_snipe,
    send_active_orders,
    send_cancel_order,
    alert_inline_query_handler, send_limit_swap, price_inline_query_handler,
)
from handlers.error import send_error
from handlers.user import send_register
from models import Order
from schemas import LimitOrder
from services.alerts import price_alert_callback

router = APIRouter()

ngrok.set_auth_token(NGROK_AUTH_TOKEN)
https_tunnel = ngrok.connect(addr=8000, bind_tls=True)
WEBHOOK_URL = f"{https_tunnel.public_url}{WEBHOOK_PATH}"


@router.on_event("startup")
async def on_startup():
    await init_database()

    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(url=WEBHOOK_URL)
    setup_handlers(dp)
    asyncio.create_task(price_alert_callback(delay=60))

    for order in Order.all():
        limit_order = LimitOrder.from_orm(order)
        asyncio.create_task(limit_order_executor(order=limit_order))
    await send_message(channel_id=TELEGRAM_CHAT_ID, message="Up and running! 👾")


@router.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()


@router.post(WEBHOOK_PATH, tags=["webhooks"])
async def bot_webhook(update: dict):
    telegram_update = types.Update(**update)
    Dispatcher.set_current(dp)
    Bot.set_current(bot)
    await dp.process_update(telegram_update)


# @router.post("/webhook/price_alert", tags=["webhooks"], status_code=201)
# async def price_alert(data: dict):
#     await send_message(channel_id=TELEGRAM_CHAT_ID, message=data['msg'])
#     return {"msg": "ok"}


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
    dispatcher.register_message_handler(send_buy, commands=["buy"])
    dispatcher.register_message_handler(send_register, commands=["register"])
    dispatcher.register_message_handler(send_balance, commands=["balance"])
    dispatcher.register_callback_query_handler(
        chart_inline_query_handler, chart_cb.filter(chart_type=["line", "candle"])
    )
    dispatcher.register_callback_query_handler(
        alert_inline_query_handler, alert_cb.filter(alert_type=["price"])
    )
    dispatcher.register_callback_query_handler(
        price_inline_query_handler, price_cb.filter(command=["price"])
    )
    dispatcher.register_callback_query_handler(kucoin_inline_query_handler)
    dispatcher.register_message_handler(send_sell, commands=["sell"])
    dispatcher.register_message_handler(send_spy, commands=["spy"])
    dispatcher.register_message_handler(send_snipe, commands=["snipe"])
    dispatcher.register_message_handler(send_limit_swap, commands=["limit"])
    dispatcher.register_message_handler(send_active_orders, commands=["active_orders"])
    dispatcher.register_message_handler(send_cancel_order, commands=["cancel_order"])

    dispatcher.register_message_handler(
        send_greeting, content_types=types.ContentTypes.NEW_CHAT_MEMBERS
    )
    dispatcher.register_errors_handler(send_error)
