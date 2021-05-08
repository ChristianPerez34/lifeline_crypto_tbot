from . import logger, cmc
from telegram.ext.callbackcontext import CallbackContext
from telegram.update import Update


def coin(update: Update, context: CallbackContext) -> None:
    """Displays crypto coin statistics for specified coin
    Args:
        update (Update): Incoming chat update for coin command
        context (CallbackContext): Bot context
    """
    logger.info("Crypto command executed")
    text = "Failed to get provided coin data"
    symbol = context.args[0].upper()
    response = cmc.cryptocurrency_quotes_latest(symbol=symbol, convert="USD")
    if response.data:
        data = response.data[symbol]
        quote = data["quote"]["USD"]
        price = "${:,}".format(float(quote["price"]))
        market_cap = "${:,}".format(float(quote["market_cap"]))
        text = (
            f"{data['slug']} ({symbol})\n\n"
            f"Price\n{price}\n\n"
            f"24h Change\n{quote['percent_change_24h']}%\n\n"
            f"Market Cap\n{market_cap}"
        )
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)
