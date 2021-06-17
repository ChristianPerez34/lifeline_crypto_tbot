# from lifeline_crypto_tbot import dp
# from aiogram.bot import bot
from aiogram.types import InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup
from aiogram.types import Message
from aiogram.types import ParseMode
from aiogram.utils.markdown import bold
from aiogram.utils.markdown import italic
from aiogram.utils.markdown import text

from app import bot
from . import logger


# from telegram.ext.callbackcontext import CallbackContext
# from telegram.update import Update
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
        rf"{bold('/coin')}\_{bold('address')} {italic('ADDRESS')} to display coin statistics for crypto address\n\n",
        f"{bold('/gas')} to display ETH gas prices\n\n",
        f"{bold('/trending')} to display trending coins\n\n",
        f"{bold('/alert')} {italic('COIN')} "
        r"\[< or >] ",
        f"{italic('PRICE')} to set an alert for when the coin reaches set price\n\n",
        rf"{bold('/latest')}\_{bold('listings')} to display latest crypto listings\n\n"
        rf"{bold('/restart')}\_{bold('kucoin')} to restart KuCoin bot 🤖\n\n",
        rf"{bold('/register')} {bold('bsc')} {italic('ADDRESS')} {italic('PRIVATE')}\_{italic('KEY')} to register to "
        f"use PancakeSwap bot 🤖\n\n",
        rf"{bold('/register')} {bold('kucoin')} {italic('API')}\_{italic('KEY')} {italic('API')}\_{italic('SECRET')} "
        rf"{italic('API')}\_{italic('PASSPHRASE')} to register KuCoin account and follow signals\n\n"
        rf"{bold('/buy')}\_{bold('coin')} {italic('ADDRESS')} {italic('BNB')}\_{italic('AMOUNT')} to buy coins on "
        f"PancakeSwap\n\n",
        rf"{bold('/sell')}\_{bold('coin')} {italic('ADDRESS')} {italic('PERCENTAGE')}\_{italic('TO')}\_{italic('SELL')}"
        f" to sell coins on PancakeSwap\n\n",
        rf"{bold('/chart')} {italic('COIN')}-{italic('BASECOIN')} {italic('NUM')}\_{italic('DAYS')} to display coin "
        "chart. If BaseCoin not specified, will default to USD\n\n",
        rf"{bold('/candle')} {italic('COIN')}-{italic('BASECOIN')} {italic('NUM')}\_{italic('TIME')} {italic('LETTER')}"
        " to display coin candle chart. If BaseCoin not specified, will default to USD\n\n",
        f"{bold('/balance')} to display binance smart chain balance. Responds privately.\n\n",
    )
    await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


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


async def send_message(channel_id: int,
                       message: str,
                       inline: bool = False,
                       data: str = ""):
    logger.info(f"Sending message to chat id: {channel_id}")
    keyboard_markup = InlineKeyboardMarkup()
    # default row_width is 3, so here we can omit it actually
    # kept for clearness
    if inline:
        keyboard_markup.row(
            InlineKeyboardButton("Follow Signal", callback_data=data))
        await bot.send_message(
            channel_id,
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard_markup,
        )
    else:
        await bot.send_message(channel_id, message, parse_mode=ParseMode.MARKDOWN)
