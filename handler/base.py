from . import logger
from telegram.ext.callbackcontext import CallbackContext
from telegram.update import Update


def start(update: Update, context: CallbackContext) -> None:
    """Starts the bot
    Args:
        update (Update): Incoming chat update for start command
        context (CallbackContext): Bot context
    """
    logger.info("Start/Help command executed")
    text = """
    /help to display available commands
    /coin [COIN] to display coin statistics
    """
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def greet(update: Update, context: CallbackContext) -> None:
    """Greets new users

    Args:
        update (Update): Incoming chat update for new members
        context (CallbackContext): Bot context
    """
    logger.info("Greeting new chat member")
    for new_user_obj in update.message.new_chat_members:
        chat_id = update.message.chat.id
        try:
            new_user = "@" + new_user_obj["username"]
        except Exception as e:
            new_user = new_user_obj["first_name"]
        text = f"Welcome fellow degen, {new_user}."
        context.bot.sendMessage(chat_id=chat_id, text=text)


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
