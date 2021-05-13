# from lifeline_crypto_tbot import dp
# from aiogram.bot import bot
from aiogram.utils.emoji import emojize
from aiogram.types import ParseMode, Message, Update
from aiogram.utils.markdown import bold, italic, text
from app import bot

# from telegram.ext.callbackcontext import CallbackContext
# from telegram.update import Update

from . import logger


async def send_welcome(message: Message):
    """Send help text on how to use bot commands

    Args:
        message (Message): Message to reply to
    """
    logger.info(message.chat.id)
    logger.info("Start/Help command executed")
    reply = text(
        "Hi! :smile:\n",
        "I'm Lifeline (Crypto)!\n\n",
        f"{bold('/help')} to display available commands\n\n",
        f"{bold('/coin')} {italic('COIN')} to display coin statistics\n\n",
        f"{bold('/coin')}\_{bold('address')} {italic('ADDRESS')} to display coin statistics for crypto address\n\n",
        f"{bold('/gas')} to display ETH gas prices\n\n",
        f"{bold('/trending')} to display trending coins\n\n",
        f"{bold('/alert')} {italic('COIN')} " "\[< or >] ",
        f"{italic('PRICE')} to set an alert for when the coin reaches set price\n\n",
        f"{bold('/latest')}\_{bold('listings')} to display latest crypto listings",
    )
    await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)


async def send_greeting(message: Message):
    """Greets new chat members

    Args:
        message (Message): Message to reply to
    """
    new_user = ""
    for new_user_obj in message.new_chat_members:
        try:
            new_user = "@" + new_user_obj["username"]
        except Exception:
            new_user = new_user_obj["first_name"]
    if new_user:
        await message.reply(text=f"Welcome fellow degen, {new_user}.")


async def send_error(update: Update, exception: Exception):
    """Exception handler

    Args:
        update (Update): Incoming chat update
        exception (Exception): Raised exception
    """

    logger.exception(exception)
    logger.debug(update)

    await update.message.reply(text="Stonks! Sorry, encountered an error.")


async def send_message(channel_id: int, text: str):

    await bot.send_message(channel_id, text)
