from telegram.ext.callbackcontext import CallbackContext
from telegram.update import Update

from . import cg
from . import crypto_cache
from . import eth
from . import logger, cmc


def coingecko_coin_lookup(ids: str, is_address: bool = False) -> dict:
    """Coin lookup in CoinGecko API

    Args:
        ids (str): id of coin to lookup
        is_address (bool): Indicates if given ids is a crypto address

    Returns:
        dict: Data from CoinGecko API
    """
    logger.info(f"Looking up price for {ids} in CoinGecko API")

    return (
        cg.get_coin_info_from_contract_address_by_id(
            id="ethereum", contract_address=ids
        )
        if is_address
        else cg.get_price(
            ids=ids,
            vs_currencies="usd",
            include_market_cap=True,
            include_24hr_change=True,
        )
    )


def coinmarketcap_coin_lookup(symbol: str) -> dict:
    """Coin lookup in CoinMarketCap API

    Args:
        symbol (str): Symbol of coin to lookup

    Returns:
        dict: Results of coin lookup
    """
    logger.info(f"Looking up price for {symbol} in CoinMarketCap API")
    response = cmc.cryptocurrency_quotes_latest(symbol=symbol, convert="usd")
    return response.data


def get_coin_stats(symbol: str) -> dict:
    """Retrieves coinstats from connected services crypto services

    Args:
        symbol (str): Cryptocurrency symbol of coin to lookup

    Returns:
        dict: Cryptocurrency coin statistics
    """
    # Search Coingecko API first
    logger.info(f"Getting coin stats for {symbol}")
    try:
        if symbol in crypto_cache.keys():
            data = coingecko_coin_lookup(crypto_cache[symbol])
        else:
            coin = [
                coin for coin in cg.get_coins_list() if coin["symbol"].upper() == symbol
            ][0]
            coin_id = coin["id"]
            crypto_cache[symbol] = coin_id
            data = coingecko_coin_lookup(coin_id)[coin_id]
        slug = crypto_cache[symbol]
        coin_stats = {
            "slug": slug,
            "price": data["usd"],
            "usd_change_24h": data["usd_24h_change"],
            "market_cap": data["usd_market_cap"],
        }
    except IndexError:
        logger.info(
            f"{symbol} not found in Coingecko. Initiated lookup on CoinMarketCap."
        )
        data = coinmarketcap_coin_lookup(symbol)[symbol]
        # crypto_cache[symbol] = data["slug"]
        quote = data["quote"]["USD"]
        coin_stats = {
            "slug": data["name"],
            "price": quote["price"],
            "usd_change_24h": quote["percent_change_24h"],
            "market_cap": quote["market_cap"],
        }
    return coin_stats


def get_coin_stats_by_address(address: str) -> dict:
    """Retrieves coin stats from connected crypto services

    Args:
        address (str): Address of coin to lookup

    Returns:
        dict: Coin statistics
    """
    # Search Coingecko API first
    logger.info(f"Getting coin stats for {address}")
    data = coingecko_coin_lookup(ids=address, is_address=True)
    # TODO: If coingecko API lookup fails, must try with other services such as CoinMarketCap
    market_data = data["market_data"]
    slug = data["name"]
    return {
        "slug": slug,
        "symbol": data["symbol"].upper(),
        "price": market_data["current_price"]["usd"],
        "usd_change_24h": market_data["price_change_percentage_24h"],
        "market_cap": market_data["market_cap"]["usd"],
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
        market_cap = "${:,}".format(float(coin_stats["market_cap"]))
        text = (
            f"{coin_stats['slug']} ({symbol})\n\n"
            f"Price\n{price}\n\n"
            f"24h Change\n{coin_stats['usd_change_24h']}%\n\n"
            f"Market Cap\n{market_cap}"
        )
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def gas(update: Update, context: CallbackContext) -> None:
    """Gets ETH gas fees

    Args:
        update (Update): Incoming chat update for ETH gas fees
        context (CallbackContext): Bot context
    """
    logger.info("ETH gas price command executed")
    gas_price = eth.get_gas_oracle()
    text = (
        "ETH Gas Prices ⛽️\n"
        f"Slow: {gas_price['SafeGasPrice']}\n"
        f"Average: {gas_price['ProposeGasPrice']}\n"
        f"Fast: {gas_price['FastGasPrice']}\n"
    )
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def coin_address(update: Update, context: CallbackContext) -> None:
    logger.info("Searching for coin by contract address")
    text = "Failed to get provided coin data"
    address = context.args[0]
    coin_stats = get_coin_stats_by_address(address=address)
    if coin_stats:
        price = "${:,}".format(float(coin_stats["price"]))
        market_cap = "${:,}".format(float(coin_stats["market_cap"]))
        text = (
            f"{coin_stats['slug']} ({coin_stats['symbol']})\n\n"
            f"Price\n{price}\n\n"
            f"24h Change\n{coin_stats['usd_change_24h']}%\n\n"
            f"Market Cap\n{market_cap}"
        )
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)
