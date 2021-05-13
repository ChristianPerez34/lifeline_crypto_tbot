import asyncio

from aiogram import Dispatcher
from aiogram import executor
from aiogram.dispatcher.webhook import get_new_configured_app
from aiohttp import web

from app import PORT, WEBAPP_HOST, bot
from app import DEV
from app import dp
from app import ENV
from app import WEBHOOK_PATH
from app import WEBHOOK_URL
from handler.base import send_error
from handler.base import send_greeting
from handler.base import send_welcome
from handler.bot.kucoin_bot import kucoin_bot
from handler.crypto import send_coin
from handler.crypto import send_coin_address
from handler.crypto import send_gas
from handler.crypto import send_latest_listings
from handler.crypto import send_price_alert
from handler.crypto import send_trending


# from handler.base import error
# from handler.base import greet
# from handler.base import start
# from handler.crypto import coin
# from handler.crypto import coin_address
# from handler.crypto import gas
# from handler.crypto import latest_listings
# from handler.crypto import priceAlert
# from handler.crypto import trending

# def main():
# updater = Updater(token, use_context=True)

# dp = updater.dispatcher

# dp.add_handler(CommandHandler("start", start))
# dp.add_handler(CommandHandler("help", start))
# dp.add_handler(CommandHandler("coin", coin))
# dp.add_handler(CommandHandler("gas", gas))
# dp.add_handler(CommandHandler("coin_address", coin_address))
# dp.add_handler(CommandHandler("trending", trending))
# dp.add_handler(CommandHandler("latest_listings", latest_listings))
# dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, greet))
# dp.add_handler(CommandHandler("alert", priceAlert))  # Accessed via /alert
# # log all errors
# dp.add_error_handler(error)

# Start the Bot
#
# if env == DEV:
#     updater.start_polling()
# else:
#     updater.start_webhook(
#         listen="0.0.0.0",
#         port=os.getenv("PORT", "8443"),
#         url_path=token,
#         webhook_url=f"{os.getenv('HEROKU_APP_URL')}/{token}",
#     )
# # updater.bot.setWebhook(f"{os.getenv('HEROKU_APP_URL')}/{token}")

# Run the bot until you press Ctrl-C or the process receives SIGINT,
# SIGTERM or SIGABRT. This should be used most of the time, since
# start_polling() is non-blocking and will stop the bot gracefully.
async def on_startup(dp: Dispatcher):
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)
    setup_handlers(dp)
    asyncio.create_task(kucoin_bot())
    # # await send_message(channel_id=TELEGRAM_CHAT_ID, text="This is a test")
    # await task


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
