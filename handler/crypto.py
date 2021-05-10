import emoji
from telegram.ext.callbackcontext import CallbackContext
from telegram.update import Update

from . import cg
from . import crypto_cache
from . import eth
from . import logger


def coingecko_coin_lookup(ids: str) -> dict:
    """Coin lookup in CoinGecko API

    Args:
        ids (str): id of coin to lookup

    Returns:
        dict: Data from CoinGecko API
    """
    logger.info(f"Looking up price for {ids} in CoinGecko API")
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
    logger.info(f"Getting coin stats for {symbol}")
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


def gas(update: Update, context: CallbackContext) -> None:
    logger.info("ETH gas price command executed")
    gas_price = eth.get_gas_oracle()
    text = ("ETH Gas Prices ⛽️\n"
            f"Slow: {gas_price['SafeGasPrice']}\n"
            f"Average: {gas_price['ProposeGasPrice']}\n"
            f"Fast: {gas_price['FastGasPrice']}\n")
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)
