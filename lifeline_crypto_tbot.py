import os

from dotenv import load_dotenv
from telegram.ext import CommandHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

from handler.base import error
from handler.base import greet
from handler.base import start
from handler.crypto import coin


def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_API")
    updater = Updater(token, use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", start))
    dp.add_handler(CommandHandler("coin", coin))
    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, greet))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    # updater.start_polling()
    updater.start_webhook(
        listen="0.0.0.0", port=os.getenv("PORT", 5000), url_path=token
    )
    updater.bot.setWebhook(f"{os.getenv('HEROKU_APP_URL')}/{token}")

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == "__main__":
    main()
