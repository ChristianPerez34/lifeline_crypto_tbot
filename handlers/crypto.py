import asyncio
import time
from decimal import Decimal
from io import BufferedReader
from io import BytesIO

import aiohttp
import dateutil.parser as dau
import pandas as pd
import plotly.figure_factory as fif
import plotly.graph_objs as go
import plotly.io as pio
from aiogram.types import CallbackQuery
from aiogram.types import Message
from aiogram.types import ParseMode
from aiogram.utils.emoji import emojize
from aiogram.utils.markdown import bold
from aiogram.utils.markdown import italic
from aiogram.utils.markdown import text
from cryptography.fernet import Fernet
from pandas import DataFrame
from pydantic.error_wrappers import ValidationError
from requests.exceptions import RequestException

from api.bsc import PancakeSwap
from api.coingecko import CoinGecko
from api.coinmarketcap import CoinMarketCap
from api.coinpaprika import CoinPaprika
from api.cryptocompare import CryptoCompare
from api.kucoin import KucoinApi
from app import bot
from bot import active_orders
from bot.kucoin_bot import kucoin_bot
from config import BUY, SELL
from config import FERNET_KEY
from config import HEADERS
from config import KUCOIN_TASK_NAME
from config import TELEGRAM_CHAT_ID
from handlers.base import send_message
from models import CryptoAlert
from models import TelegramGroupMember
from schemas import Coin, Alert, User, TradeCoin, Chart, CandleChart
from utils import all_same
from . import eth
from . import logger


def get_coin_stats(symbol: str) -> dict:
    """Retrieves coin stats from connected services crypto services

    Args:
        symbol (str): Cryptocurrency symbol of coin to lookup

    Returns:
        dict: Cryptocurrency coin statistics
    """
    # Search CoinGecko API first
    logger.info(f"Getting coin stats for {symbol}")
    coin_gecko = CoinGecko()
    coin_market_cap = CoinMarketCap()
    try:
        coin_id = coin_gecko.get_coin_id(symbol=symbol)
        data = coin_gecko.coin_lookup(ids=coin_id)
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
            f"{symbol} not found in CoinGecko. Initiated lookup on CoinMarketCap."
        )
        data = coin_market_cap.coin_lookup(symbol)
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
    # Search CoinGecko API first
    logger.info(f"Getting coin stats for {address}")
    coin_gecko = CoinGecko()
    data = coin_gecko.coin_lookup(ids=address, is_address=True)
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
    try:
        coin = Coin(symbol=args[0].upper())
        symbol = coin.symbol
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
    except IndexError as e:
        logger.exception(e)
        reply = f"⚠️ Please provide a crypto code: \n{bold('/coin')} {italic('COIN')}"
    except ValidationError as e:
        logger.exception(e)
        error_message = e.args[0][0].exc
        reply = f"⚠️ {error_message}"

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
    try:
        coin = Coin(address=args[0])
        address = coin.address
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
    except IndexError as e:
        logger.exception(e)
        reply = f"⚠️ Please provide a crypto address: \n{bold('/coin')}_{bold('address')} {italic('ADDRESS')}"
    except ValueError as e:
        logger.exception(e)
        reply = f"⚠️ Could not find coin"

    await message.reply(text=reply)


async def send_trending(message: Message) -> None:
    """Replies to command with trending crypto coins

    Args:
        message (Message): Message to reply to
    """
    logger.info("Retrieving trending addresses from CoinGecko")
    coin_gecko = CoinGecko()
    coin_market_cap = CoinMarketCap()
    coin_gecko_trending_coins = "\n".join([
        f"{coin['item']['name']} ({coin['item']['symbol']})"
        for coin in coin_gecko.get_trending_coins()
    ])
    coin_market_cap_trending_coins = "\n".join(
        await coin_market_cap.get_trending_coins())

    reply = (f"Trending 🔥\n\nCoinGecko\n\n{coin_gecko_trending_coins}\n\n"
             f"CoinMarketCap\n\n{coin_market_cap_trending_coins}")
    await message.reply(text=reply)


async def send_price_alert(message: Message) -> None:
    """Replies to message with alert when coin passes expected mark price

    Args:
        message (Message): Message to reply to
    """
    logger.info("Setting a new price alert")
    args = message.get_args().split()

    try:
        alert = Alert(symbol=args[0].upper(), sign=args[1], price=args[2])
        crypto = alert.symbol
        sign = alert.sign
        price = alert.price

        coin_stats = get_coin_stats(symbol=crypto)

        crypto_alert = await CryptoAlert.create(symbol=crypto, sign=sign, price=price)

        asyncio.create_task(price_alert_callback(alert=crypto_alert, delay=15))
        reply = f"⏳ I will send you a message when the price of {crypto} reaches ${price}, \n"
        reply += f"the current price of {crypto} is ${float(coin_stats['price'])}"
    except IndexError as e:
        logger.exception(e)
        reply = "⚠️ Please provide a crypto code and a price value: /alert [COIN] [<,>] [PRICE]"
    except ValidationError as e:
        logger.exception(e)
        error_message = e.args[0][0].exc
        reply = f"⚠️ {error_message}"
    await message.reply(text=reply)


async def price_alert_callback(alert: CryptoAlert, delay: int) -> None:
    """Repetitive task that continues monitoring market for alerted coin mark price until alert is displayed

    Args:
        alert (CryptoAlert): CryptoAlert model
        delay (int): Interval of time to wait in seconds
    """
    crypto = alert.symbol
    sign = alert.sign
    price = alert.price

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
            price = "${:,}".format(price)
            spot_price = "${:,}".format(spot_price)
            if dip:
                response = f":( {crypto} has dipped below {price} and is currently at {spot_price}."
            else:
                response = f"👋 {crypto} has surpassed {price} and has just reached {spot_price}!"
            await send_message(channel_id=TELEGRAM_CHAT_ID, message=response)
            await alert.delete()

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
        user = User.from_orm(await TelegramGroupMember.get(id=user.id))

        if (user.kucoin_api_key and user.kucoin_api_secret
                and user.kucoin_api_passphrase):
            fernet = Fernet(FERNET_KEY)
            api_key = fernet.decrypt(user.kucoin_api_key.encode()).decode()
            api_secret = fernet.decrypt(
                user.kucoin_api_secret.encode()).decode()
            api_passphrase = fernet.decrypt(
                user.kucoin_api_passphrase.encode()).decode()
            kucoin_api = KucoinApi(api_key=api_key,
                                   api_secret=api_secret,
                                   api_passphrase=api_passphrase)
            orders = kucoin_api.get_open_stop_order()

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
            reply = "Restarted KuCoin Bot 🤖"
        else:
            logger.info("User does not have a registered KuCoin account")
            reply = "⚠ Sorry, please register KuCoin account"
    else:
        logger.info("User is not admin")
        reply = "⚠ Sorry, this command can only be executed by an admin"
    await message.reply(text=reply)


async def send_buy_coin(message: Message) -> None:
    """
    Command to buy coins in PancakeSwap
    Args:
        message (Message): Telegram chat message

    """
    logger.info("Started buy coin command")

    telegram_user = message.from_user
    args = message.get_args().split()

    try:
        user = User.from_orm(await TelegramGroupMember.get(id=telegram_user.id))
        if user:
            trade = TradeCoin(address=args[0], amount=args[1], side=BUY)
            pancake_swap = PancakeSwap(address=user.bsc_address,
                                       key=user.bsc_private_key)
            reply = pancake_swap.swap_tokens(token=trade.address,
                                             amount_to_spend=trade.amount,
                                             side=trade.side)
        else:
            reply = "⚠ Sorry, you must register prior to using this command."
    except IndexError as e:
        logger.exception(e)
        reply = "⚠️ Please provide a crypto token address and amount of BNB to spend: /buy_coin [ADDRESS] [AMOUNT]"
    except ValidationError as e:
        logger.exception(e)
        error_message = e.args[0][0].exc
        reply = f"⚠️ {error_message}"

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

    try:
        user = User.from_orm(await TelegramGroupMember.get(id=telegram_user.id))
        if user:
            trade = TradeCoin(address=args[0], amount=args[1], side=SELL)
            percentage = float(args[1])
            if 0 < percentage < 101:
                percentage_to_sell = trade.amount / 100
                pancake_swap = PancakeSwap(address=user.bsc_address,
                                           key=user.bsc_private_key)
                reply = pancake_swap.swap_tokens(
                    token=trade.address,
                    amount_to_spend=percentage_to_sell,
                    side=trade.side)
            else:
                reply = "⚠ Sorry, incorrect percentage value. Choose a value between 1 and 100 inclusive"
        else:
            reply = "⚠ Sorry, you must register prior to using this command."
    except IndexError as e:
        logger.exception(e)
        reply = "⚠️ Please provide a crypto token address and amount of BNB to spend: /sell_coin [ADDRESS] [AMOUNT]"
    except ValidationError as e:
        logger.exception(e)
        error_message = e.args[0][0].exc
        reply = f"⚠️ {error_message}"

    await message.reply(text=reply)


async def send_chart(message: Message):
    """Replies to command with coin chart for given crypto symbol and amount of days

    Args:
        message (Message): Message to reply to
    """
    logger.info("Searching for coin market data for chart")
    coin_gecko = CoinGecko()
    args = message.get_args().split()
    base_coin = "USD"
    reply = ""

    try:
        chart = Chart(ticker=args[0], time_frame=args[1])
        pair = chart.ticker.split('-')
        symbol = pair[0]
        base_coin = pair[1]
        time_frame = chart.time_frame

        coin_id = coin_gecko.get_coin_id(symbol)
        market = coin_gecko.coin_market_lookup(coin_id, time_frame, base_coin)

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
            line=dict(color="rgb(22, 96, 167)", width=2),
        )

        margin_l = 140
        tick_format = "0.8f"

        max_value = df_price["Price"].max()
        if max_value > 0.9:
            if max_value > 999:
                margin_l = 110
                tick_format = "0,.0f"
            else:
                margin_l = 115
                tick_format = "0.2f"

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
                ticksuffix="  ",
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
                "y0": market["prices"][-1][1],
                "y1": market["prices"][-1][1],
                "line": {
                    "color": "rgb(50, 171, 96)",
                    "width": 1,
                    "dash": "dot"
                },
            }],
        )

        fig = go.Figure(data=[price, volume], layout=layout)
        fig["layout"]["yaxis2"].update(tickformat=tick_format)
    except IndexError as e:
        logger.exception(e)
        reply = text(
            f"⚠️ Please provide a valid crypto symbol and amount of days: "
            f"\n{bold('/chart')} {italic('SYMBOL')} {italic('DAYS')}")
    except ValidationError as e:
        logger.exception(e)
        error_message = e.args[0][0].exc
        reply = f"⚠️ {error_message}"

    if reply:
        await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)
    else:
        logger.info("Exporting chart as image")
        await message.reply_photo(
            photo=BufferedReader(
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))),
            parse_mode=ParseMode.MARKDOWN,
        )


async def send_candle_chart(message: Message):
    """Replies to command with coin candle chart for given crypto symbol and amount of time

    Args:
        message (Message): Message to reply to
    """

    args = message.get_args().split()
    reply = ""

    try:
        candle_chart = CandleChart(ticker=args[0], time_frame=args[1], resolution=args[2])
        pair = candle_chart.ticker.split('-')
        symbol, base_coin = pair[0], pair[1]

        time_frame = candle_chart.time_frame
        resolution = candle_chart.resolution

        logger.info("Searching for coin historical data for candle chart")
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
                open_ = [value["open"] for value in ohlcv]
                high = [value["high"] for value in ohlcv]
                low = [value["low"] for value in ohlcv]
                close = [value["close"] for value in ohlcv]
                time_ = [value["time"] for value in ohlcv]

            if not ohlcv or all_same(open_, high, low, close):

                reply = text(
                    f"{symbol} not found on CryptoCompare. Initiated lookup on CoinPaprika."
                    f" Data may not be as complete as CoinGecko or CMC")
                await message.reply(text=emojize(reply),
                                    parse_mode=ParseMode.MARKDOWN)
                reply = ""

                cp_ohlc = CoinPaprika().get_list_coins()

                for close in cp_ohlc:
                    if close["symbol"] == symbol:

                        # Current datetime in seconds
                        t_now = time.time()
                        # Convert chart time span to seconds
                        time_frame = int(time_frame) * 24 * 60 * 60
                        # Start datetime for chart in seconds
                        t_start = t_now - int(time_frame)

                        ohlcv = CoinPaprika().get_historical_ohlc(
                            close["id"],
                            int(t_start),
                            end=int(t_now),
                            quote=base_coin.lower(),
                            limit=366,
                        )

                        if ohlcv:
                            break

                open_ = [value["open"] for value in ohlcv]
                high = [value["high"] for value in ohlcv]
                low = [value["low"] for value in ohlcv]
                close = [value["close"] for value in ohlcv]
                time_ = [
                    time.mktime(dau.parse(value["time_close"]).timetuple())
                    for value in ohlcv
                ]

            margin_l = 140
            tick_format = "0.8f"

            max_value = max(high)
            if max_value > 0.9:
                if max_value > 999:
                    margin_l = 120
                    tick_format = "0,.0f"
                else:
                    margin_l = 125
                    tick_format = "0.2f"

            fig = fif.create_candlestick(open_, high, low, close,
                                         pd.to_datetime(time_, unit="s"))

            fig["layout"]["yaxis"].update(tickformat=tick_format,
                                          tickprefix="   ",
                                          ticksuffix="  ")

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
                "y0": close[-1],
                "y1": close[-1],
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
    except IndexError as e:
        logger.exception(e)
        reply = text(
            f"⚠️ Please provide a valid crypto symbol and time followed by desired timeframe letter:\n"
            f" m - Minute\n h - Hour\n d - Day\n \n{bold('/candle')} {italic('SYMBOL')} "
            f"{italic('NUMBER')} {italic('LETTER')}")
    except ValidationError as e:
        logger.exception(e)
        error_message = e.args[0][0].exc
        reply = f"⚠️ {error_message}"

    if reply:
        await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)
    else:
        logger.info("Exporting chart as image")
        await message.reply_photo(
            photo=BufferedReader(
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))),
            parse_mode=ParseMode.MARKDOWN,
        )


async def kucoin_inline_query_handler(query: CallbackQuery) -> None:
    """
    Inline query handler for KuCoin Futures signals
    Args:
        query (CallbackQuery): Query

    """
    await query.answer(text="")
    user = query.from_user
    username = user.username
    logger.info(f"{username} following KuCoin signal")
    user = User.from_orm(await TelegramGroupMember.get(id=user.id))
    if user.kucoin_api_key and user.kucoin_api_secret and user.kucoin_api_passphrase:
        fernet = Fernet(FERNET_KEY)
        api_key = fernet.decrypt(user.kucoin_api_key.encode()).decode()
        api_secret = fernet.decrypt(user.kucoin_api_secret.encode()).decode()
        api_passphrase = fernet.decrypt(
            user.kucoin_api_passphrase.encode()).decode()
        kucoin_api = KucoinApi(api_key=api_key,
                               api_secret=api_secret,
                               api_passphrase=api_passphrase)
        logger.info("Retrieving user balance")
        balance = kucoin_api.get_balance()

        # Use ten percent of available balance
        ten_percent_port = balance * Decimal(0.10)
        data = query.data.split(";")
        symbol = f"{data[0]}M"
        symbol = symbol.replace("BTC", "XBT")
        side = data[1]
        leverage = 10
        try:
            ticker = kucoin_api.get_ticker(symbol=symbol)
            size = (ten_percent_port / Decimal(ticker["price"])) * leverage
            kucoin_api.create_market_order(symbol=symbol,
                                           side=side,
                                           size=int(size),
                                           lever=str(leverage))
            reply = f"@{username} successfully followed signal"
        except RequestException as e:
            logger.exception(e)
            reply = "⚠️ Unable to follow signal"

    else:
        reply = "⚠️ Please register KuCoin account to follow signals"
    await send_message(channel_id=query.message.chat.id, message=reply)


async def send_balance(message: Message):
    logger.info("Retrieving account balance")
    user_id = message.from_user.id
    user = User.from_orm(await TelegramGroupMember.get(id=user_id))
    reply = "Account Balance 💲"
    pancake_swap = PancakeSwap(address=user.bsc_address,
                               key=user.bsc_private_key)
    account_holdings = await pancake_swap.get_account_token_holdings(
        address=pancake_swap.address)
    for k in account_holdings.keys():
        coin = account_holdings[k]
        token = coin["address"]

        # Quantity in wei used to calculate price
        quantity = pancake_swap.get_token_balance(token)
        if quantity > 0:
            token_price = pancake_swap.get_token_price(address=token)
            price = quantity / token_price

            # Quantity in correct format as seen in wallet
            quantity /= Decimal(10 ** (18 - (coin["decimals"] % 18)))
            usd_amount = f"${price.quantize(Decimal('0.01'))}"
            reply += f"\n\n{k}: {quantity} ({usd_amount})"

    await send_message(channel_id=user_id, message=reply)
