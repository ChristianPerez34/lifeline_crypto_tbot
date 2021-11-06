from aiogram.types import Message
from cryptography.fernet import Fernet
from pony.orm import OrmError
from pydantic import ValidationError

from app import bot
from app import logger
from config import FERNET_KEY, RegisterTypes
from handlers.base import send_message
from models import TelegramGroupMember
from schemas import BinanceChain, User, EthereumChain, MaticChain, CoinBaseExchange


async def register_network(
        register_type: str, address: str, private_key: str, user_id: int
) -> dict:
    fernet = Fernet(FERNET_KEY)
    data = {"id": user_id}
    if register_type == RegisterTypes.BSC.value:
        data.update(
            {
                "bsc": BinanceChain(  # type: ignore
                    address=address,
                    private_key=fernet.encrypt(private_key.encode()).decode(),
                    telegram_group_member=user_id,
                ),
            }
        )
    elif register_type == RegisterTypes.ETH.value:
        data.update(
            {
                "eth": EthereumChain(  # type: ignore
                    address=address,
                    private_key=fernet.encrypt(private_key.encode()).decode(),
                    telegram_group_member=user_id,
                ),
            }
        )
    else:
        data.update(
            {
                "matic": MaticChain(  # type: ignore
                    address=address,
                    private_key=fernet.encrypt(private_key.encode()).decode(),
                    telegram_group_member=user_id,
                ),
            }
        )
    return data


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

    exclude = set()
    user_id = telegram_user.id

    if register_type in (
            RegisterTypes.BSC.value,
            RegisterTypes.ETH.value,
            RegisterTypes.MATIC.value,
    ):
        address, private_key = tuple(args[1:])
        data = await register_network(
            register_type=register_type,
            address=address,
            private_key=private_key,
            user_id=user_id,
        )
        exclude = {"kucoin_api_key", "kucoin_api_secret", "kucoin_api_passphrase"}
    elif register_type == RegisterTypes.COINBASE.value:
        if len(args) != 4:
            is_error = True
            text = (
                "⚠️ Please provide CoinBase Pro API Key, Secret and Passphrase: /register coinbase [API_KEY] "
                "[API_SECRET] [API_PASSPHRASE]"
            )
        else:
            fernet = Fernet(FERNET_KEY)
            api_key, api_secret, api_passphrase = args[1:]

            data.update(
                {
                    "id": user_id,
                    "coinbase": CoinBaseExchange(  # type: ignore
                        api_key=fernet.encrypt(api_key.encode()).decode(),
                        api_secret=fernet.encrypt(api_secret.encode()).decode(),
                        api_passphrase=fernet.encrypt(api_passphrase.encode()).decode(),
                        telegram_group_member=user_id
                    ),
                }
            )
            exclude = {"kucoin_api_key", "kucoin_api_secret", "kucoin_api_passphrase"}
    elif register_type == RegisterTypes.KUCOIN.value:
        if len(args) != 4:
            is_error = True
            text = (
                "⚠️ Please provide KuCoin API Key, Secret and Passphrase: /register kucoin [API_KEY] "
                "[API_SECRET] [API_PASSPHRASE]"
            )
        else:
            fernet = Fernet(FERNET_KEY)
            api_key, api_secret, api_passphrase = tuple(args[1:])
            data.update(
                {
                    "id": user_id,
                    "kucoin_api_key": fernet.encrypt(api_key.encode()).decode(),
                    "kucoin_api_secret": fernet.encrypt(api_secret.encode()).decode(),
                    "kucoin_api_passphrase": fernet.encrypt(
                        api_passphrase.encode()
                    ).decode(),
                }
            )
            exclude = {"bsc_address", "bsc_private_key"}

    else:
        is_error = True
        text = (
            "⚠️ Stonks! Sorry about that, couldn't identify type of account to register. Specify account type: "
            "/register [bsc] or [kucoin] "
        )

    if not is_error:
        try:
            user = User(**data)
            TelegramGroupMember.create_or_update(data=user.dict(exclude=exclude))
            text = f"Successfully registered @{telegram_user.username}"
        except OrmError as e:
            logger.info("Failed to register user")
            logger.exception(e)
        except ValidationError as e:
            logger.exception(e)
            error_message = e.args[0][0].exc
            text = f"⚠️ {error_message}"
    await send_message(channel_id=chat_id, message=text)
