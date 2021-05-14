import asyncio

import aiohttp
import pandas as pd
from aiogram.types import Message
from aiogram.types import ParseMode
from aiogram.utils.markdown import bold
from aiogram.utils.markdown import italic

from . import cg
from . import cmc
from . import crypto_cache
from . import eth
from . import logger
from app import bot
from bot import KUCOIN_TASK_NAME
from bot import TELEGRAM_CHAT_ID
from bot.kucoin_bot import kucoin_bot
from handler.base import send_message


def coingecko_coin_lookup(ids: str, is_address: bool = False) -> dict:
    """Coin lookup in CoinGecko API

    Args:
        ids (str): id of coin to lookup
        is_address (bool): Indicates if given ids is a crypto address

    Returns:
        dict: Data from CoinGecko API
    """
    logger.info(f"Looking up price for {ids} in CoinGecko API")

    return (cg.get_coin_info_from_contract_address_by_id(
        id="ethereum", contract_address=ids) if is_address else cg.get_price(
            ids=ids,
            vs_currencies="usd",
            include_market_cap=True,
            include_24hr_change=True,
        ))


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
            coin_id = crypto_cache[symbol]
            data = coingecko_coin_lookup(coin_id)[coin_id]
        else:
            coin = [
                coin for coin in cg.get_coins_list()
                if coin["symbol"].upper() == symbol
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
    market_data = data["market_data"]
    slug = data["name"]
    return {
        "slug": slug,
        "symbol": data["symbol"].upper(),
        "price": market_data["current_price"]["usd"],
        "usd_change_24h": market_data["price_change_percentage_24h"],
        "market_cap": market_data["market_cap"]["usd"],
    }


async def send_coin(message: Message) -> None:
    """Replies to command with crypto coin statistics for specified coin

    Args:
        message (Message): Message to reply to
    """
    logger.info("Crypto command executed")
    reply = "Failed to get provided coin data"
    args = message.get_args().split()
    if len(args) != 1:
        reply = f"⚠️ Please provide a crypto code: \n{bold('/coin')} {italic('COIN')}"
    else:
        symbol = args[0].upper()
        coin_stats = get_coin_stats(symbol=symbol)
        if coin_stats:
            price = "${:,}".format(float(coin_stats["price"]))
            market_cap = "${:,}".format(float(coin_stats["market_cap"]))
            reply = (f"{coin_stats['slug']} ({symbol})\n\n"
                     f"Price\n{price}\n\n"
                     f"24h Change\n{coin_stats['usd_change_24h']}%\n\n"
                     f"Market Cap\n{market_cap}")
    await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


async def send_gas(message: Message) -> None:
    """Replies to command with eth gas fees

    Args:
        message (Message): Message to reply to
    """
    logger.info("ETH gas price command executed")
    gas_price = eth.get_gas_oracle()
    reply = ("ETH Gas Prices ⛽️\n"
             f"Slow: {gas_price['SafeGasPrice']}\n"
             f"Average: {gas_price['ProposeGasPrice']}\n"
             f"Fast: {gas_price['FastGasPrice']}\n")
    await message.reply(text=reply)


async def send_coin_address(message: Message) -> None:
    """Replies to command with coin stats for given crypto contract address

    Args:
        message (Message): Message to reply to
    """
    logger.info("Searching for coin by contract address")
    args = message.get_args().split()
    if len(args) != 1:
        reply = f"⚠️ Please provide a crypto address: \n{bold('/coin')}_{bold('address')} {italic('ADDRESS')}"
    else:
        address = args[0]
        coin_stats = get_coin_stats_by_address(address=address)
        if coin_stats:
            price = "${:,}".format(float(coin_stats["price"]))
            market_cap = "${:,}".format(float(coin_stats["market_cap"]))
            reply = (f"{coin_stats['slug']} ({coin_stats['symbol']})\n\n"
                     f"Price\n{price}\n\n"
                     f"24h Change\n{coin_stats['usd_change_24h']}%\n\n"
                     f"Market Cap\n{market_cap}")
    await message.reply(text=reply)


async def send_trending(message: Message) -> None:
    """Replies to command with trending crypto coins

    Args:
        message (Message): Message to reply to
    """
    logger.info("Retrieving trending addresses from CoinGecko")
    trending_coins = "\n".join(
        [coin["item"]["symbol"] for coin in cg.get_search_trending()["coins"]])
    reply = f"Trending 🔥\n\n{trending_coins}"
    await message.reply(text=reply)


async def send_price_alert(message: Message) -> None:
    """Replies to message with alert when coin passes expected mark price

    Args:
        message (Message): Message to reply to
    """
    logger.info("Setting a new price alert")
    args = message.get_args().split()

    if len(args) > 2:
        crypto = args[0].upper()
        sign = args[1]
        price = args[2]

        coin_stats = get_coin_stats(symbol=crypto)

        asyncio.create_task(
            priceAlertCallback(context=[crypto, sign, price], delay=15))
        response = f"⏳ I will send you a message when the price of {crypto} reaches ${price}, \n"
        response += f"the current price of {crypto} is ${float(coin_stats['price'])}"
    else:
        response = "⚠️ Please provide a crypto code and a price value: /alert [COIN] [<,>] [PRICE]"
    await message.reply(text=response)


async def priceAlertCallback(context: list, delay: int) -> None:
    """Repetitive task that continues monitoring market for alerted coin mark price until alert is displayed

    Args:
        message (Message): Message to reply to
        context (list): Alert context
        delay (int): Interval of time to wait in seconds
    """
    crypto = context[0]
    sign = context[1]
    price = context[2]

    send = False
    dip = False

    while not send:
        coin_stats = get_coin_stats(symbol=crypto)

        spot_price = coin_stats["price"]

        if sign == "<":
            if float(price) >= float(spot_price):
                send = True
                dip = True
        else:
            if float(price) <= float(spot_price):
                send = True

        if send:
            if dip:
                response = f":( {crypto} has dipped below {'${:,}'.format(price)} and is currently at {'${:,}'.format(spot_price)}."

            else:
                response = f"👋 {crypto} has surpassed {'${:,}'.format(price)} and has just reached {'${:,}'.format(spot_price)}!"
            await send_message(channel_id=TELEGRAM_CHAT_ID, text=response)

        await asyncio.sleep(delay)


async def send_latest_listings(message: Message) -> None:
    """Replies to command with latest crypto listings

    Args:
        message (Message): Message to reply to
    """
    logger.info("Retrieving latest crypto listings from CoinGecko")
    count = 5
    reply = "Latest Listings 🤑\n"
    headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(
                "https://www.coingecko.com/en/coins/recently_added",
                headers=headers) as response:
            df = pd.read_html(await response.text(), flavor="bs4")[0]

            for row in df.itertuples():
                if count == 0:
                    break

                words = row.Coin.split()
                words = sorted(set(words), key=words.index)
                words[-1] = f"({words[-1]})"

                coin = " ".join(words)
                reply += f"\n{coin}"
                count -= 1

    await message.reply(text=reply)


async def send_restart_kucoin_bot(message: Message) -> None:
    logger.info("Verifying user is admin")
    user = message.from_user
    administrators = [
        admin.user for admin in await bot.get_chat_administrators(
            chat_id=TELEGRAM_CHAT_ID)
    ]
    if user in administrators:
        logger.info("Restarting KuCoin Bot")
        tasks = asyncio.all_tasks()
        [
            task.cancel() for task in tasks
            if task.get_name() == KUCOIN_TASK_NAME
        ]
        asyncio.create_task(kucoin_bot(), name=KUCOIN_TASK_NAME)
        reply = f"Restarted KuCoin Bot 🤖"
    else:
        reply = "⚠️ Sorry, this command can only be executed by an admin"
    await message.reply(text=reply)
