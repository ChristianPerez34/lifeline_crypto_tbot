import asyncio
import concurrent
import io
import time
from decimal import Decimal
from io import BytesIO

import aiohttp
import dateutil.parser as dau
import pandas as pd
import plotly.figure_factory as fif
import plotly.graph_objs as go
import plotly.io as pio
from aiogram.types import Message
from aiogram.types import ParseMode, CallbackQuery
from aiogram.utils.emoji import emojize
from aiogram.utils.markdown import bold
from aiogram.utils.markdown import italic
from aiogram.utils.markdown import link
from aiogram.utils.markdown import text
from cryptography.fernet import Fernet
from pandas import DataFrame
from uniswap import InsufficientBalance
from uniswap import Uniswap
from web3 import Web3

from api.coinpaprika import CoinPaprika
from api.cryptocompare import CryptoCompare
from api.kucoin import KucoinApi
from app import bot
from bot import active_orders
from bot.kucoin_bot import kucoin_bot
from config import BINANCE_SMART_CHAIN_URL, TELEGRAM_CHAT_ID, KUCOIN_TASK_NAME
from config import BNB_ADDRESS
from config import BUY
from config import FERNET_KEY
from config import PANCAKESWAP_FACTORY_ADDRESS
from config import PANCAKESWAP_ROUTER_ADDRESS
from config import SELL
from handlers.base import send_message
from models import TelegramGroupMember
from utils import all_same
from . import cg
from . import cmc
from . import coingecko_coin_lookup_cache
from . import eth
from . import logger

HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"
}


def coingecko_coin_lookup(ids: str, is_address: bool = False) -> dict:
    """Coin lookup in CoinGecko API

    Args:
        ids (str): id of coin to lookup
        is_address (bool): Indicates if given ids is a crypto address

    Returns:
        dict: Data from CoinGecko API
    """
    logger.info(f"Looking up price for {ids} in CoinGecko API")
    try:
        data = (cg.get_coin_info_from_contract_address_by_id(
            id="ethereum", contract_address=ids)
                if is_address else cg.get_coin_by_id(id=ids))
    except Exception:
        data = (cg.get_coin_info_from_contract_address_by_id(
            id="binance", contract_address=ids)
                if is_address else cg.get_coin_by_id(id=ids))
    return data


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
        coin_id = get_coingecko_coin_id(symbol=symbol)
        data = coingecko_coin_lookup(coin_id)
        market_data = data["market_data"]
        coin_stats = {
            "slug": data["name"],
            "contract_address": data.get("contract_address", ""),
            "website": data["links"]["homepage"][0],
            "price": market_data["current_price"]["usd"],
            "usd_change_24h": market_data["price_change_percentage_24h"],
            "usd_change_7d": market_data["price_change_percentage_7d"],
            "market_cap": market_data["market_cap"]["usd"],
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
            "usd_change_7d": quote["percent_change_7d"],
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
        "contract_address": data["contract_address"],
        "website": data["links"]["homepage"][0],
        "symbol": data["symbol"].upper(),
        "price": market_data["current_price"]["usd"],
        "usd_change_24h": market_data["price_change_percentage_24h"],
        "usd_change_7d": market_data["price_change_percentage_7d"],
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
            reply = f"{coin_stats['slug']} ({symbol})\n\n"

            if coin_stats["contract_address"]:
                reply += f"{coin_stats['contract_address']}\n\n"

            if "website" in coin_stats:
                reply += f"{coin_stats['website']}\n\n"
            reply += (f"Price\n{price}\n\n"
                      f"24h Change\n{coin_stats['usd_change_24h']}%\n\n"
                      f"7D Change\n{coin_stats['usd_change_7d']}%\n\n"
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
        reply = text(
            f"⚠️ Please provide a crypto address: \n{bold('/coin')}_{bold('address')} {italic('ADDRESS')}"
        )
    else:
        address = args[0]
        coin_stats = get_coin_stats_by_address(address=address)
        price = "${:,}".format(float(coin_stats["price"]))
        market_cap = "${:,}".format(float(coin_stats["market_cap"]))
        reply = f"{coin_stats['slug']} ({coin_stats['symbol']})\n\n"

        if "contract_address" in coin_stats:
            reply += f"{coin_stats['contract_address']}\n\n"

        if "website" in coin_stats:
            reply += f"{coin_stats['website']}\n\n"
        reply += (f"Price\n{price}\n\n"
                  f"24h Change\n{coin_stats['usd_change_24h']}%\n\n"
                  f"7D Change\n{coin_stats['usd_change_7d']}%\n\n"
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
    reply = "CoinGecko Latest Listings 🤑\n"

    async with aiohttp.ClientSession() as session:
        async with session.get(
                "https://www.coingecko.com/en/coins/recently_added",
                headers=HEADERS) as response:
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
        count = 5
        logger.info("Retrieving latest crypto listings from CoinMarketCap")
        reply += "\n\nCoinMarketCap Latest Listings 🤑\n\n"
        async with session.get("https://coinmarketcap.com/new/",
                               headers=HEADERS) as response:
            df = pd.read_html(await response.text(), flavor="bs4")[0]
            for index, row in df.iterrows():
                if count == 0:
                    break

                coin = row.Name.replace(str(index + 1), "-").split("-")
                name, symbol = coin[0], f"({coin[1]})"
                reply += f"{name} {symbol}\n"
                count -= 1

    await message.reply(text=reply)


async def send_restart_kucoin_bot(message: Message) -> None:
    logger.info("Verifying user is admin")
    take_profit, stop_loss = "", ""
    user = message.from_user
    administrators = [
        admin.user for admin in await bot.get_chat_administrators(
            chat_id=TELEGRAM_CHAT_ID)
    ]

    if user in administrators:
        logger.info(f"User {user.username} is admin. Restarting KuCoin Bot")
        user = await TelegramGroupMember.filter(telegram_user_id=user.id).first()

        if user.kucoin_api_key and user.kucoin_api_secret and user.kucoin_api_passphrase:
            fernet = Fernet(FERNET_KEY)
            api_key = fernet.decrypt(user.kucoin_api_key.encode()).decode()
            api_secret = fernet.decrypt(user.kucoin_api_secret.encode()).decode()
            api_passphrase = fernet.decrypt(user.kucoin_api_passphrase.encode()).decode()
            kucoin_api = KucoinApi(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
            orders = [order for order in kucoin_api.get_open_stop_order()]

            for position in kucoin_api.get_all_position():
                if position["isOpen"]:
                    symbol = position["symbol"]
                    position_orders = [
                        order for order in orders if order["symbol"] == symbol
                    ]

                    for position_order in position_orders:
                        stop_price = position_order["stopPrice"]

                        if (position_order["stopPriceType"] == "TP"
                                and position_order["stop"] == "up"):
                            take_profit = stop_price
                        else:
                            stop_loss = stop_price
                    symbol = symbol[:-1]
                    symbol = symbol.replace("XBTUSDT", "BTCUSDT")
                    entry = position["avgEntryPrice"]
                    mark_price = position["markPrice"]
                    unrealized_pnl = position["unrealisedPnl"]
                    side = ("LONG" if
                            (entry < mark_price and unrealized_pnl > 0) or
                            (entry > mark_price and unrealized_pnl < 0) else
                            "SHORT")
                    active_orders.update({
                        symbol: {
                            "entry": entry,
                            "side": side,
                            "take_profit": take_profit,
                            "stop_loss": stop_loss,
                        }
                    })
            asyncio.create_task(kucoin_bot(), name=KUCOIN_TASK_NAME)
            reply = f"Restarted KuCoin Bot 🤖"
        else:
            logger.info("User does not have a registered KuCoin account")
            reply = "⚠ Sorry, please register KuCoin account"
    else:
        logger.info("User is not admin")
        reply = "⚠ Sorry, this command can only be executed by an admin"
    await message.reply(text=reply)


def swap_tokens(token: str, amount_to_spend: float, side: str,
                user: TelegramGroupMember) -> str:
    """
    Swaps crypto coins on PancakeSwap
    Args:
        token (str): Address of coin to buy/sell
        amount_to_spend (float): Amount in BNB expected to spend/receive. When selling will read as percentage
        side (str): Indicates if user wants to buy or sell coins
        user (TelegramGroupMember): Telegram user

    Returns: Reply to message

    """
    web3 = Web3(Web3.HTTPProvider(BINANCE_SMART_CHAIN_URL))

    if web3.isConnected():
        fernet = Fernet(FERNET_KEY)
        user_address = web3.toChecksumAddress(user.bsc_address)
        private_key = fernet.decrypt(user.bsc_private_key).decode()
        token = web3.toChecksumAddress(token)

        pancakeswap_wrapper = Uniswap(
            user_address,
            private_key,
            version=2,
            web3=web3,
            factory_contract_addr=PANCAKESWAP_FACTORY_ADDRESS,
            router_contract_addr=PANCAKESWAP_ROUTER_ADDRESS,
        )
        try:
            if side == BUY:
                amount_to_spend = web3.toWei(amount_to_spend, "ether")
                txn_hash = web3.toHex(
                    pancakeswap_wrapper.make_trade(BNB_ADDRESS, token,
                                                   amount_to_spend,
                                                   user_address))
            else:
                balance = web3.fromWei(
                    pancakeswap_wrapper.get_token_balance(token), "ether")
                amount_to_spend = web3.toWei(
                    balance * Decimal(amount_to_spend), "ether")
                txn_hash = web3.toHex(
                    pancakeswap_wrapper.make_trade_output(
                        token, BNB_ADDRESS, amount_to_spend, user_address))

            txn_hash_url = f"https://bscscan.com/tx/{txn_hash}"
            reply = f"Transactions completed successfully. {link(title='View Transaction', url=txn_hash_url)}"
        except InsufficientBalance as e:
            reply = "⚠️ Insufficient balance. Top up you BNB balance and try again. "
    else:
        reply = "⚠ Sorry, I was unable to connect to the Binance Smart Chain. Try again later."
    return reply


async def send_buy_coin(message: Message) -> None:
    """
    Command to buy coins in PancakeSwap
    Args:
        message (Message): Telegram chat message

    """
    logger.info("Started buy coin command")

    telegram_user = message.from_user
    args = message.get_args().split()

    if len(args) != 2:
        reply = "⚠️ Please provide a crypto token address and amount of BNB to spend: /buy_coin [ADDRESS] [AMOUNT]"
    else:
        user = await TelegramGroupMember.filter(
            telegram_user_id=telegram_user.id).first()
        if user:
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
            loop = asyncio.get_event_loop()
            reply = await loop.run_in_executor(executor, swap_tokens, args[0],
                                               float(args[1]), BUY, user)
        else:
            reply = "⚠ Sorry, you must register prior to using this command."

    await message.reply(text=reply)


async def send_sell_coin(message: Message) -> None:
    """
    Command to sell coins in PancakeSwap
    Args:
        message (Message): Message to reply to

    """
    logger.info("Started sell coin command")
    telegram_user = message.from_user
    args = message.get_args().split()

    if len(args) != 2:
        reply = "⚠️ Please provide a crypto token address and amount of BNB to spend: /sell_coin [ADDRESS] [AMOUNT]"
    else:
        user = await TelegramGroupMember.filter(
            telegram_user_id=telegram_user.id).first()
        if user:
            percentage = float(args[1])
            if 0 < percentage < 101:
                percentage_to_sell = float(args[1]) / 100
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
                loop = asyncio.get_event_loop()
                reply = await loop.run_in_executor(executor, swap_tokens,
                                                   args[0], percentage_to_sell,
                                                   SELL, user)
            else:
                reply = "⚠ Sorry, incorrect percentage value. Choose a value between 1 and 100 inclusive"
        else:
            reply = "⚠ Sorry, you must register prior to using this command."

    await message.reply(text=reply)


def coingecko_coin_market_lookup(ids: str, time_frame: int, base_coin: str) -> dict:
    """Coin lookup in CoinGecko API for Market Chart

    Args:
        ids (str): id of coin to lookup
        time_frame (int): Indicates number of days for data span

    Returns:
        dict: Data from CoinGecko API
    """
    logger.info(f"Looking up chart data for {ids} in CoinGecko API")

    return cg.get_coin_market_chart_by_id(ids, base_coin, time_frame)


def get_coingecko_coin_id(symbol: str) -> str:
    """Retrieves coinstats from connected services crypto services

    Args:
        symbol (str): Cryptocurrency symbol of coin to lookup

    Returns:
        str: coin id of the cryptocurrency
    """
    # Search Coingecko API first
    logger.info(f"Getting coin ID for {symbol}")

    if symbol in coingecko_coin_lookup_cache.keys():
        coin_id = coingecko_coin_lookup_cache[symbol]

    else:
        coin = [
            coin for coin in cg.get_coins_list()
            if coin["symbol"].upper() == symbol
        ][0]
        coin_id = coin["id"]
        coingecko_coin_lookup_cache[symbol] = coin_id

    return coin_id


async def send_chart(message: Message):
    """Replies to command with coin chart for given crypto symbol and amount of days

    Args:
        message (Message): Message to reply to
    """
    logger.info("Searching for coin market data for chart")
    args = message.get_args().split()
    base_coin = 'USD'
    reply = ''

    if len(args) != 2:
        reply = text(
            f"⚠️ Please provide a valid crypto symbol and amount of days: \n{bold('/chart')} {italic('SYMBOL')} {italic('DAYS')}"
        )
    else:

        if "-" in args[0]:
            pair = args[0].split("-", 1)
            base_coin = pair[1].upper()
            symbol = pair[0].upper()
        else:
            symbol = args[0].upper()

        if symbol == base_coin:
            reply = text(f"Can't compare *{symbol}* to itself. Will default base coin to USD")
            await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)
            reply = ''
            base_coin = 'USD'

        time_frame = args[1]

        coin_id = get_coingecko_coin_id(symbol)
        market = coingecko_coin_market_lookup(coin_id, time_frame, base_coin)

        logger.info("Creating chart layout")
        # Volume
        df_volume = DataFrame(market["total_volumes"],
                              columns=["DateTime", "Volume"])
        df_volume["DateTime"] = pd.to_datetime(df_volume["DateTime"],
                                               unit="ms")
        volume = go.Scatter(x=df_volume.get("DateTime"),
                            y=df_volume.get("Volume"),
                            name="Volume")

        # Price
        df_price = DataFrame(market["prices"], columns=["DateTime", "Price"])
        df_price["DateTime"] = pd.to_datetime(df_price["DateTime"], unit="ms")
        price = go.Scatter(
            x=df_price.get("DateTime"),
            y=df_price.get("Price"),
            yaxis="y2",
            name="Price",
            line=dict(color=("rgb(22, 96, 167)"), width=2),
        )

        margin_l = 140
        tickformat = "0.8f"

        max_value = df_price["Price"].max()
        if max_value > 0.9:
            if max_value > 999:
                margin_l = 110
                tickformat = "0,.0f"
            else:
                margin_l = 115
                tickformat = "0.2f"

        layout = go.Layout(
            paper_bgcolor="rgb(233,233,233)",
            plot_bgcolor="rgb(233,233,233)",
            autosize=False,
            width=800,
            height=600,
            margin=go.layout.Margin(l=margin_l, r=50, b=85, t=100, pad=4),
            yaxis=dict(domain=[0, 0.20]),
            yaxis2=dict(
                title=dict(text=base_coin, font=dict(size=18)),
                domain=[0.25, 1],
                tickprefix="   ",
                ticksuffix=f"  ",
            ),
            title=dict(text=symbol, font=dict(size=26)),
            legend=dict(orientation="h",
                        yanchor="top",
                        xanchor="center",
                        y=1.05,
                        x=0.45),
            shapes=[{
                "type": "line",
                "xref": "paper",
                "yref": "y2",
                "x0": 0,
                "x1": 1,
                "y0": market["prices"][len(market["prices"]) - 1][1],
                "y1": market["prices"][len(market["prices"]) - 1][1],
                "line": {
                    "color": "rgb(50, 171, 96)",
                    "width": 1,
                    "dash": "dot"
                },
            }],
        )

        fig = go.Figure(data=[price, volume], layout=layout)
        fig["layout"]["yaxis2"].update(tickformat=tickformat)

    if reply:
        await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)
    else:
        logger.info("Exporting chart as image")
        await message.reply_photo(
            photo=io.BufferedReader(
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))),
            parse_mode=ParseMode.MARKDOWN,
        )


async def send_candlechart(message: Message):
    """Replies to command with coin candlechart for given crypto symbol and amount of time

    Args:
        message (Message): Message to reply to
    """

    args = message.get_args().split()
    reply = ""

    if len(args) != 3:
        reply = text(
            f"⚠️ Please provide a valid crypto symbol and time followed by desired timeframe letter:\n"
            f" m - Minute\n h - Hour\n d - Day\n \n{bold('/candle')} {italic('SYMBOL')} "
            f"{italic('NUMBER')} {italic('LETTER')}")
    else:

        base_coin = "USD"

        if "-" in args[0]:
            pair = args[0].split("-", 1)
            base_coin = pair[1].upper()
            symbol = pair[0].upper()
        else:
            symbol = args[0].upper()

        if symbol == base_coin:
            reply = text(f"Can't compare *{symbol}* to itself. Will default base coin to USD")
            await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)
            reply = ''
            base_coin = 'USD'

        time_frame = args[1]
        res = args[2].lower()

        # Time frame
        if len(args) > 1:
            if res == "m":
                resolution = "MINUTE"
            elif res == "h":
                resolution = "HOUR"
            else:
                resolution = "DAY"
        logger.info("Searching for coin historical data for candlechart")
        if resolution == "MINUTE":
            ohlcv = CryptoCompare().get_historical_ohlcv_minute(
                symbol, base_coin, time_frame)
        elif resolution == "HOUR":
            ohlcv = CryptoCompare().get_historical_ohlcv_hourly(
                symbol, base_coin, time_frame)
        elif resolution == "DAY":
            ohlcv = CryptoCompare().get_historical_ohlcv_daily(
                symbol, base_coin, time_frame)
        else:
            ohlcv = CryptoCompare().get_historical_ohlcv_hourly(
                symbol, base_coin, time_frame)

        if ohlcv["Response"] == "Error":
            if ohlcv["Message"] == "limit is larger than max value.":
                reply = text(
                    f" Time frame can't be larger than {bold('2000')} DAYS data points"
                )

            else:
                reply = text(f"Error: {ohlcv['Message']}")
        else:

            ohlcv = ohlcv["Data"]

            if ohlcv:
                o = [value["open"] for value in ohlcv]
                h = [value["high"] for value in ohlcv]
                l = [value["low"] for value in ohlcv]
                c = [value["close"] for value in ohlcv]
                t = [value["time"] for value in ohlcv]

            if not ohlcv or all_same(o, h, l, c):

                reply = text(
                    f"{symbol} not found on CryptoCompare. Initiated lookup on CoinPaprika."
                    f" Data may not be as complete as CoinGecko or CMC")
                await message.reply(text=emojize(reply),
                                    parse_mode=ParseMode.MARKDOWN)
                reply = ""

                cp_ohlc = CoinPaprika().get_list_coins()

                for c in cp_ohlc:
                    if c["symbol"] == symbol:

                        # Current datetime in seconds
                        t_now = time.time()
                        # Convert chart time span to seconds
                        time_frame = int(time_frame) * 24 * 60 * 60
                        # Start datetime for chart in seconds
                        t_start = t_now - int(time_frame)

                        ohlcv = CoinPaprika().get_historical_ohlc(
                            c["id"],
                            int(t_start),
                            end=int(t_now),
                            quote=base_coin.lower(),
                            limit=366,
                        )

                        if ohlcv:
                            cp_api = True
                            break
                        else:
                            return

                o = [value["open"] for value in ohlcv]
                h = [value["high"] for value in ohlcv]
                l = [value["low"] for value in ohlcv]
                c = [value["close"] for value in ohlcv]
                t = [
                    time.mktime(dau.parse(value["time_close"]).timetuple())
                    for value in ohlcv
                ]

            margin_l = 140
            tickformat = "0.8f"

            max_value = max(h)
            if max_value > 0.9:
                if max_value > 999:
                    margin_l = 120
                    tickformat = "0,.0f"
                else:
                    margin_l = 125
                    tickformat = "0.2f"

            fig = fif.create_candlestick(o, h, l, c, pd.to_datetime(t,
                                                                    unit="s"))

            fig["layout"]["yaxis"].update(tickformat=tickformat,
                                          tickprefix="   ",
                                          ticksuffix=f"  ")

            fig["layout"].update(
                title=dict(text=symbol, font=dict(size=26)),
                yaxis=dict(title=dict(text=base_coin, font=dict(size=18)), ),
            )

            fig["layout"].update(shapes=[{
                "type": "line",
                "xref": "paper",
                "yref": "y",
                "x0": 0,
                "x1": 1,
                "y0": c[len(c) - 1],
                "y1": c[len(c) - 1],
                "line": {
                    "color": "rgb(50, 171, 96)",
                    "width": 1,
                    "dash": "dot",
                },
            }])

            fig["layout"].update(
                paper_bgcolor="rgb(233,233,233)",
                plot_bgcolor="rgb(233,233,233)",
                autosize=False,
                width=800,
                height=600,
                margin=go.layout.Margin(l=margin_l, r=50, b=85, t=100, pad=4),
            )

    if reply:
        await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)
    else:
        logger.info("Exporting chart as image")
        await message.reply_photo(
            photo=io.BufferedReader(
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))),
            parse_mode=ParseMode.MARKDOWN,
        )


async def kucoin_inline_query_handler(query: CallbackQuery):
    # Ideally gets kucoin keys from user
    user = await TelegramGroupMember.filter(telegram_user_id=query.from_user.id).first()
    if user.kucoin_api_key and user.kucoin_api_secret and user.kucoin_api_passphrase:
        fernet = Fernet(FERNET_KEY)
        api_key = fernet.decrypt(user.kucoin_api_key.encode()).decode()
        api_secret = fernet.decrypt(user.kucoin_api_secret.encode()).decode()
        api_passphrase = fernet.decrypt(user.kucoin_api_passphrase.encode()).decode()
        kucoin_api = KucoinApi(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
        balance = kucoin_api.get_balance()

        # Use ten percent of available balance
        ten_percent_port = balance * Decimal(0.10)
        reply = str(ten_percent_port)
    else:
        reply = f"⚠️ Please register KuCoin account to follow signals"

    await query.answer(text=reply)
    answer_data = query.data

#     TODO: Allow user to follow trade
