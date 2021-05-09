from telegram.ext.callbackcontext import CallbackContext
from telegram.update import Update

from . import cg
from . import cmc
from . import crypto_cache
from . import logger


def coingecko_coin_lookup(ids: str) -> dict:
    """Coin lookup in CoinGecko API

    Args:
        ids (str): id of coin to lookup

    Returns:
        dict: Data from CoinGecko API
    """
    return cg.get_price(
        ids=ids,
        vs_currencies="usd",
        include_market_cap=True,
        include_24hr_change=True,
    )


def get_coin_stats(symbol: str) -> dict:
    """Retrieves coinstats from connected services crypto services

    Args:
        symbol (str): Cryptocurrency symbol of coin to lookup

    Returns:
        dict: Cryptocurrency coin statistics
    """
    # Search Coingecko API first
    if symbol in crypto_cache.keys():
        data = coingecko_coin_lookup(crypto_cache[symbol])
    else:
        coin = [
            coin for coin in cg.get_coins_list()
            if coin["symbol"].upper() == symbol
        ][0]
        crypto_cache[symbol] = coin["id"]
        data = coingecko_coin_lookup(crypto_cache[symbol])
    # TODO: If coingecko API lookup fails, must try with other services such as CoinMarketCap
    slug = crypto_cache[symbol]
    quote = data[slug]
    return {
        "slug": slug,
        "price": quote["usd"],
        "usd_change_24h": quote["usd_24h_change"],
        "market_cap": quote["usd_market_cap"],
    }


def coin(update: Update, context: CallbackContext) -> None:
    """Displays crypto coin statistics for specified coin
    Args:
        update (Update): Incoming chat update for coin command
        context (CallbackContext): Bot context
    """
    logger.info("Crypto command executed")
    text = "Failed to get provided coin data"
    symbol = context.args[0].upper()
    coin_stats = get_coin_stats(symbol=symbol)
    if coin_stats:
        price = "${:,}".format(float(coin_stats["price"]))
        change_24h = "${:,}".format(float(coin_stats["usd_change_24h"]))
        market_cap = "${:,}".format(float(coin_stats["market_cap"]))
        text = (f"{coin_stats['slug']} ({symbol})\n\n"
                f"Price\n{price}\n\n"
                f"24h Change\n{coin_stats['usd_change_24h']}%\n\n"
                f"Market Cap\n{market_cap}")
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def priceAlert(update: Update, context: CallbackContext) -> None:
    if len(context.args) > 2:
        crypto = context.args[0].upper()
        sign = context.args[1]
        price = context.args[2]
        
        coin_stats = get_coin_stats(symbol=crypto)
        context.job_queue.run_repeating(priceAlertCallback, interval=15, first=15, context=[crypto, sign, price, update.message.chat_id])
        
        response = f"⏳ I will send you a message when the price of {crypto} reaches ${price}, \n"
        response += f"the current price of {crypto} is ${float(coin_stats['price'])}"
    else:
        response = '⚠️ Please provide a crypto code and a price value: \n<i>/price_alert {crypto code} {> / &lt;} {price}</i>'
    
    context.bot.send_message(chat_id=update.effective_chat.id, text=response)


def priceAlertCallback(context):
    crypto = context.job.context[0]
    sign = context.job.context[1]
    price = context.job.context[2]
    chat_id = context.job.context[3]
    

    send = False
    coin_stats = get_coin_stats(symbol=crypto)
    spot_price = coin_stats["price"]

    if sign == '<':
        if float(price) >= float(spot_price):
            send = True
    else:
        if float(price) <= float(spot_price):
            send = True

    if send:
        response = f'👋 {crypto} has surpassed ${price} and has just reached <b>${spot_price}</b>!'

        context.job.schedule_removal()

        context.bot.send_message(chat_id=chat_id, text=response)