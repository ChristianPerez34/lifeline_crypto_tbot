import random
from io import BufferedReader

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ParseMode, InputFile

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
    pdf = InputFile("BotCommands.pdf")
    await message.reply_document(document=pdf, caption="PDF detailing available bot commands",
                                 parse_mode=ParseMode.MARKDOWN)


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
