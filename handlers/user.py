from aiogram.types import Message
from cryptography.fernet import Fernet

from app import bot
from config import FERNET_KEY
from handlers import logger
from handlers.base import send_message
from models import TelegramGroupMember


async def send_register(message: Message) -> None:
    """Replies to command with trending crypto coins

    Args:
        message (Message): Message to reply to
    """
    logger.info("Registering new user")
    chat_id = message.chat.id
    telegram_user = message.from_user
    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)

    args = message.get_args().split()
    if len(args) != 2:
        text = "⚠️ Please provide BNB smart chain address and private key: /register [ADDRESS] [PRIVATE_KEY]"
    else:
        address, private_key = args[0], args[1]
        try:
            fernet = Fernet(FERNET_KEY)
            private_key = fernet.encrypt(private_key.encode())
            await TelegramGroupMember.create(telegram_user_id=telegram_user.id, bsc_address=address,
                                             bsc_private_key=private_key)
            text = f"Successfully registered @{telegram_user.username}"
        except Exception as e:
            logger.info("Failed to register user")
            logger.exception(e)
            text = "⚠ Stonks! Sorry about that. We seem to have encountered some issues registering your account."
    await send_message(channel_id=chat_id, text=text)
