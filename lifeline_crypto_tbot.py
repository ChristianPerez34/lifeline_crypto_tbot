import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, Updater

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def start(update: Update, context: CallbackContext) -> None:
    """[summary]

    Args:
        update (Update): Incoming chat update for start command
        context (CallbackContext): bot context
    """
    logger.info("Start/Help command executed")
    text = """
    /help to display available commands
    """
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def error(update: Update, context: CallbackContext) -> None:
    """Captures any bot error

    Args:
        update ([type]): Incoming chat update for errors
        context ([type]): bot context
    """
    logger.warning('Update "%s" caused error "%s"', update, context.error)
    context.bot.send_message(
        chat_id=update.effective_chat.id, text="Stonks! Sorry, encountered an error."
    )


def main():
    load_dotenv()
    updater = Updater(os.getenv("TELEGRAM_BOT_API"), use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", start))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == "__main__":
    main()
