from fastapi import FastAPI

from app.routers.webhook import router

app = FastAPI()
app.include_router(router)

# async def on_startup(dispatcher: Dispatcher):
#     """Bot startup actions
#
#     Args:
#         dispatcher (Dispatcher): Bot dispatcher
#     """
#     await init_database()
#
#     for alert in CryptoAlert.all():
#         asyncio.create_task(price_alert_callback(alert=alert, delay=15))
#     for order in Order.all():
#         limit_order = LimitOrder.from_orm(order)
#         asyncio.create_task(limit_order_executor(order=limit_order))
#     setup_handlers(dispatcher)
#
#     await send_message(channel_id=TELEGRAM_CHAT_ID, message="Up and running! 👾")
#
#
# async def on_shutdown(_):
#     """Displays message to let users know bot is offline"""
#     await send_message(
#         channel_id=TELEGRAM_CHAT_ID, message="Going offline! Be right back."
#     )


# if __name__ == "__main__":
#     import os
#
#     print(os.getcwd())
#     app = FastAPI()
#     app.include_router(router)
#     uvicorn.run(app, host="0.0.0.0", port=8000)
