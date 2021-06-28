from aiogram.types import Message
from cryptography.fernet import Fernet
from pydantic import ValidationError
from tortoise.exceptions import BaseORMException

from app import bot
from config import FERNET_KEY
from config import RegisterTypes
from handlers import logger
from handlers.base import send_message
from models import TelegramGroupMember
from schemas import User


async def send_register(message: Message) -> None:
    """Replies to command with trending crypto coins

    Args:
        message (Message): Message to reply to
    """
    logger.info("Registering new user")
    data = {}
    is_error = False
    chat_id = message.chat.id
    telegram_user = message.from_user
    text = "⚠ Stonks! Sorry about that. We seem to have encountered some issues registering your account."
    await bot.delete_message(chat_id=chat_id, message_id=message.message_id)

    args = message.get_args().split()
    register_type = args[0].upper()
    fernet = Fernet(FERNET_KEY)
    exclude = {}

    if register_type == RegisterTypes.BSC.value:

        if len(args) != 3:
            is_error = True
            text = "⚠️ Please provide BNB smart chain address and private key: /register bsc [ADDRESS] [PRIVATE_KEY]"
        else:
            address, private_key = tuple(args[1:])
            data.update({
                "id":
                telegram_user.id,
                "bsc_address":
                address,
                "bsc_private_key":
                fernet.encrypt(private_key.encode()).decode(),
            })
            exclude = {'kucoin_api_key', 'kucoin_api_secret', 'kucoin_api_passphrase'}
    elif register_type == RegisterTypes.KUCOIN.value:
        if len(args) != 4:
            is_error = True
            text = (
                "⚠️ Please provide KuCoin API Key, Secret and Passphrase: /register kucoin [API_KEY] "
                "[API_SECRET] [API_PASSPHRASE]")
        else:
            api_key, api_secret, api_passphrase = tuple(args[1:])
            data.update({
                "id":
                    telegram_user.id,
                "kucoin_api_key":
                    fernet.encrypt(api_key.encode()).decode(),
                "kucoin_api_secret":
                    fernet.encrypt(api_secret.encode()).decode(),
                "kucoin_api_passphrase":
                    fernet.encrypt(api_passphrase.encode()).decode(),
            })
            exclude = {'bsc_address', 'bsc_private_key'}

    else:
        is_error = True
        text = (
            "⚠️ Stonks! Sorry about that, couldn't identify type of account to register. Specify account type: "
            "/register [bsc] or [kucoin] ")

    if not is_error:
        try:
            user = User(**data)
            await TelegramGroupMember().create_or_update(data=user.dict(exclude=exclude))
            text = f"Successfully registered @{telegram_user.username}"
        except BaseORMException as e:
            logger.info("Failed to register user")
            logger.exception(e)
        except ValidationError as e:
            logger.exception(e)
            error_message = e.args[0][0].exc
            text = f"⚠️ {error_message}"
    await send_message(channel_id=chat_id, message=text)
