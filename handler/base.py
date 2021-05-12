# from lifeline_crypto_tbot import dp
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, Message, Update
from aiogram.utils.markdown import bold, code, italic, text

# from telegram.ext.callbackcontext import CallbackContext
# from telegram.update import Update

from . import logger


async def send_welcome(message: Message):
    """Send help text on how to use bot commands

    Args:
        message (Message): Message to reply to
    """
    logger.info("Start/Help command executed")
    reply = text(
        "Hi! :smile:\n",
        "I'm Lifeline (Crypto)!\n\n",
        f"{bold('/help')} to display available commands\n\n",
        f"{bold('/coin')} {italic('COIN')} to display coin statistics\n\n",
        f"{bold('/gas')} to display ETH gas prices\n\n",
        f"{bold('/trending')} to display trending coins\n\n",
        f"{bold('/alert')} {italic('COIN')} " "\[< or >] ",
        f"{italic('PRICE')} to set an alert for when the coin reaches set price\n\n"
        f"{bold('/latest')}**\_**{bold('listings')} to display latest crypto listings",
    )
    await message.reply(emojize(reply), parse_mode=ParseMode.MARKDOWN)


async def send_greeting(message: Message):
    """Greets new chat members

    Args:
        message (Message): Message to reply to
    """
    for new_user_obj in message.new_chat_members:
        try:
            new_user = "@" + new_user_obj["username"]
        except Exception:
            new_user = new_user_obj["first_name"]
    await message.reply(f"Welcome fellow degen, {new_user}.")


async def send_error(update: Update, exception: Exception):
    """Exception handler

    Args:
        update (Update): Incoming chat update
        exception (Exception): Raised exception
    """

    logger.exception(exception)
    logger.debug(update)

    update.message.reply("Stonks! Sorry, encountered an error.")
