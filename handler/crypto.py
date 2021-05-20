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


def trending(update: Update, context: CallbackContext) -> None:
    """Retrieves trending coins from CoinGecko

    Args:
        update (Update): Incoming chat update for trending coins
        context (CallbackContext): Bot context
    """
    logger.info("Retrieving trending addresses from CoinGecko")
    text = "Failed to get provided coin data"
    trending_coins = "\n".join(
        [coin["item"]["symbol"] for coin in cg.get_search_trending()["coins"]]
    )
    text = f"Trending 🔥\n\n{trending_coins}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def priceAlert(update: Update, context: CallbackContext) -> None:
    if len(context.args) > 2:
        crypto = context.args[0].upper()
        sign = context.args[1]
        price = context.args[2]

        coin_stats = get_coin_stats(symbol=crypto)

        context.job_queue.run_repeating(
            priceAlertCallback,
            interval=30,
            first=15,
            context=[crypto, sign, price, update.message.chat_id],
        )

        response = f"⏳ I will send you a message when the price of {crypto} reaches ${price}, \n"
        response += f"the current price of {crypto} is ${float(coin_stats['price'])}"
    else:
        response = "⚠️ Please provide a crypto code and a price value: /alert [COIN] [<,>] [PRICE]"

    context.bot.send_message(chat_id=update.effective_chat.id, text=response)


def priceAlertCallback(context):
    crypto = context.job.context[0]
    sign = context.job.context[1]
    price = context.job.context[2]
    chat_id = context.job.context[3]

    send = False
    dip = False
    coin_stats = get_coin_stats(symbol=crypto)

    spot_price = coin_stats['price']

    if sign == "<":
        if float(price) >= float(spot_price):
            send = True
            dip = True
    else:
        if float(price) <= float(spot_price):
            send = True

    if send:
        if dip:
            response = f":( {crypto} has dipped below ${price} and is currently at ${spot_price}."

        else:
            response = (
                f"👋 {crypto} has surpassed ${price} and has just reached ${spot_price}!"
            )

        context.job.schedule_removal()

        context.bot.send_message(chat_id=chat_id, text=response)
