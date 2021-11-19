import asyncio

from aiogram import executor
from aiogram.dispatcher.webhook import get_new_configured_app
from aiohttp import web

from app import dp, bot
from app.routers.webhook import setup_handlers
from bot.bsc_order import limit_order_executor
from config import TELEGRAM_CHAT_ID, WEBHOOK_PATH, WEBHOOK_URL, WEBAPP_PORT, WEBAPP_HOST
from handlers import init_database
from handlers.base import send_message
from models import Order
from schemas import LimitOrder
from services.alerts import price_alert_callback


async def on_startup(_):
    """Bot startup actions"""
    await init_database()

    webhook_info = await bot.get_webhook_info()

    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    setup_handlers(dp)
    asyncio.create_task(price_alert_callback(delay=60))

    for order in Order.all():
        limit_order = LimitOrder.from_orm(order)
        asyncio.create_task(limit_order_executor(order=limit_order))
    await send_message(channel_id=TELEGRAM_CHAT_ID, message="Up and running! 👾")


async def on_shutdown(_):
    """Displays message to let users know bot is offline"""
    await send_message(
        channel_id=TELEGRAM_CHAT_ID, message="Going offline! Be right back."
    )
    await bot.session.close()


if __name__ == "__main__":
    app = get_new_configured_app(dispatcher=dp, path=WEBHOOK_PATH)

    executor = executor.Executor(dispatcher=dp, skip_updates=True)
    executor.set_web_app(application=app)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
