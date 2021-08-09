import random
from io import BufferedReader

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ParseMode
from aiogram.utils.markdown import bold, italic, text

from app import bot
from app import logger
from config import GREETINGS


async def send_welcome(message: Message) -> None:
    """Send help text on how to use bot commands

    Args:
        message (Message): Message to reply to
    """
    logger.info("Chat ID: %s", message.chat.id)
    logger.info("Start/Help command executed")
    reply = text(
        "Hi! 😄\n",
        "I'm Lifeline (Crypto)!\n\n",
        f"{bold('/help')} to display available commands\n\n",
        f"{bold('/price')} {italic('COIN')} to display coin statistics\n\n",
        rf"{bold('/price')}\_{bold('address')} {italic('ADDRESS')} {italic('PLATFORM')} to display coin statistics for "
        f"crypto address. {italic('PLATFORM')} is optional\n\n",
        f"{bold('/gas')} to display ETH gas prices\n\n",
        f"{bold('/trending')} to display trending coins\n\n",
        f"{bold('/alert')} {italic('COIN')} " r"\[< or >] ",
        f"{italic('PRICE')} to set an alert for when the coin reaches set price\n\n",
        rf"{bold('/latest')}\_{bold('listings')} to display latest crypto listings"
        "\n\n",
        rf"{bold('/restart')}\_{bold('kucoin')} to restart KuCoin bot 🤖" "\n\n",
        rf"{bold('/register')} {bold('bsc')} {italic('ADDRESS')} {italic('PRIVATE')}\_{italic('KEY')} to register to "
        f"use PancakeSwap bot 🤖\n\n",
        rf"{bold('/register')} {bold('kucoin')} {italic('API')}\_{italic('KEY')} {italic('API')}\_{italic('SECRET')} "
        rf"{italic('API')}\_{italic('PASSPHRASE')} to register KuCoin account and follow signals"
        "\n\n"
        rf"{bold('/buy')}\_{bold('coin')} {italic('ADDRESS')} {italic('BNB')}\_{italic('AMOUNT')} to buy coins on "
        f"PancakeSwap\n\n",
        rf"{bold('/sell')}\_{bold('coin')} {italic('ADDRESS')} to sell coins on PancakeSwap"
        "\n\n",
        rf"{bold('/chart')} {italic('COIN')}-{italic('BASECOIN')} {italic('NUM')}\_{italic('DAYS')} to display coin "
        "chart. If BaseCoin not specified, will default to USD\n\n",
        rf"{bold('/candle')} {italic('COIN')}-{italic('BASECOIN')} {italic('NUM')}\_{italic('TIME')} {italic('LETTER')}"
        " to display coin candle chart. If BaseCoin not specified, will default to USD\n\n",
        f"{bold('/balance')} to display binance smart chain balance. Responds privately.\n\n",
        f"{bold('/spy')} {italic('ADDRESS')} to display some of the accounts holdings.\n\n",
        rf"{bold('/snipe')} {italic('ADDRESS')} {italic('BNB')}\_{italic('AMOUNT')} to snipe token. Uses high gas!\n\n",
        rf"{bold('/limit')} {italic('ACTION')} {italic('ADDRESS')} {italic('TARGET')}\_{italic('PRICE')} "
        rf"{italic('BNB')}\_{italic('AMOUNT')} to create a limit order. Actions: buy|sell|stop\n\n",
    )
    await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


async def send_greeting(message: Message) -> None:
    """Greets new chat members

    Args:
        message (Message): Message to reply to
    """
    logger.info("Greeting new user")
    new_user = ""
    for new_user_obj in message.new_chat_members:
        try:
            new_user = "@" + new_user_obj["username"]
        except KeyError:
            new_user = new_user_obj["first_name"]
    if new_user:
        greeting = random.choice(GREETINGS).format(new_user)
        await message.reply(text=greeting)


async def send_message(
    channel_id: int, message: str, inline: bool = False, data: str = ""
) -> None:
    logger.info("Sending message to chat id: %s", channel_id)
    keyboard_markup = InlineKeyboardMarkup()
    # default row_width is 3, so here we can omit it actually
    # kept for clearness
    if inline:
        keyboard_markup.row(InlineKeyboardButton("Follow Signal", callback_data=data))
        await bot.send_message(
            channel_id,
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard_markup,
        )
    else:
        await bot.send_message(channel_id, message, parse_mode=ParseMode.MARKDOWN)


async def send_photo(chat_id: int, caption: str, photo: BufferedReader):
    await bot.send_photo(
        chat_id=chat_id, caption=caption, photo=photo, parse_mode=ParseMode.MARKDOWN
    )
