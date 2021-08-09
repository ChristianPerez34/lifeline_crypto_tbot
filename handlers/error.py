from aiogram.types import Update

from app import logger


async def send_error(update: Update, exception: Exception) -> bool:
    """Exception handlers

    Args:
        update (Update): Incoming chat update
        exception (Exception): Raised exception

    Returns:
        bool: True
    """

    logger.exception(exception)
    logger.debug(update)

    await update.message.reply(text="Stonks! Sorry, encountered an error.")
    return True
