import asyncio
import time
from decimal import Decimal
from io import BufferedReader, BytesIO
from itertools import chain
from urllib.parse import urlparse

import aiohttp
import dateutil.parser as dau
import plotly.figure_factory as fif
import plotly.graph_objs as go
import plotly.io as pio
from aiogram.types import CallbackQuery, Message, ParseMode
from aiogram.utils.emoji import emojize
from aiogram.utils.markdown import bold, italic, text
from cryptography.fernet import Fernet
from inflection import titleize
from pandas import DataFrame, read_html, to_datetime
from pydantic.error_wrappers import ValidationError
from requests.exceptions import RequestException
from web3.exceptions import ContractLogicError

from api.bsc import BinanceSmartChain, PancakeSwap
from api.coingecko import CoinGecko
from api.coinmarketcap import CoinMarketCap
from api.coinpaprika import CoinPaprika
from api.cryptocompare import CryptoCompare
from api.eth import UniSwap
from api.kucoin import KucoinApi
from app import bot, logger
from bot import active_orders
from bot.bsc_order import limit_order_executor
from bot.bsc_sniper import pancake_swap_sniper
from bot.kucoin_bot import kucoin_bot
from config import BUY, FERNET_KEY, HEADERS, KUCOIN_TASK_NAME, SELL, TELEGRAM_CHAT_ID
from handlers.base import send_message, send_photo
from models import CryptoAlert, TelegramGroupMember, Order
from schemas import CandleChart, Chart, Coin, TokenAlert, TradeCoin, User, LimitOrder, Platform
from utils import all_same
from . import ether_scan


def get_coin_stats(symbol: str) -> list:
    """Retrieves coin stats from connected services crypto services

    Args:
        symbol (str): Cryptocurrency symbol of coin to lookup

    Returns:
        dict: Cryptocurrency coin statistics
    """
    # Search CoinGecko API first
    logger.info("Getting coin stats for %s", symbol)
    coin_stats_list = []
    coin_gecko = CoinGecko()
    coin_market_cap = CoinMarketCap()
    try:
        coin_ids = coin_gecko.get_coin_ids(symbol=symbol)

        for coin_id in coin_ids:
            data = coin_gecko.coin_lookup(ids=coin_id)
            market_data = data["market_data"]
            links = data["links"]
            coin_stats = {
                "token_name": data["name"],
                "website": links["homepage"][0],
                "explorers": [
                    f"[{urlparse(link).hostname}]({link})"
                    for link in links["blockchain_site"]
                    if link
                ],
                "price": "${:,}".format(float(market_data["current_price"]["usd"])),
                "24h_change": f"{market_data['price_change_percentage_24h']}%",
                "7d_change": f"{market_data['price_change_percentage_7d']}%",
                "30d_change": f"{market_data['price_change_percentage_30d']}%",
                "market_cap": "${:,}".format(float(market_data["market_cap"]["usd"])),
            }
            coin_stats_list.append(coin_stats)
    except IndexError:
        logger.info(
            "%s not found in CoinGecko. Initiated lookup on CoinMarketCap.", symbol
        )
        coin_lookup = coin_market_cap.coin_lookup(symbol)

        for coin in coin_lookup:
            data = coin_lookup[coin]
            quote = data["quote"]["USD"]

            for key in quote:
                if quote[key] is None:
                    quote[key] = 0
            coin_stats = {
                "token_name": data["name"],
                "price": "${:,}".format(quote["price"]),
                "24h_change": f"{quote['percent_change_24h']}%",
                "7d_change": f"{quote['percent_change_7d']}%",
                "30d_change": f"{quote['percent_change_30d']}%",
                "market_cap": "${:,}".format(quote["market_cap"]),
            }
            coin_stats_list.append(coin_stats)
    return coin_stats_list


def get_coin_stats_by_address(address: str) -> dict:
    """Retrieves coin stats from connected crypto services

    Args:
        address (str): Address of coin to lookup

    Returns:
        dict: Coin statistics
    """
    # Search CoinGecko API first
    logger.info("Getting coin stats for %s", address)
    coin_gecko = CoinGecko()
    data = coin_gecko.coin_lookup(ids=address, is_address=True)
    market_data = data["market_data"]
    links = data["links"]
    return {
        "token_name": data["name"],
        "website": links["homepage"][0],
        "explorers": [
            f"[{urlparse(link).hostname}]({link})"
            for link in links["blockchain_site"]
            if link
        ],
        "price": "${:,}".format(float(market_data["current_price"]["usd"])),
        "24h_change": f"{market_data['price_change_percentage_24h']}%",
        "7d_change": f"{market_data['price_change_percentage_7d']}%",
        "30d_change": f"{market_data['price_change_percentage_30d']}%",
        "market_cap": "${:,}".format(float(market_data["market_cap"]["usd"])),
    }


async def send_price(message: Message) -> None:
    """Replies to command with crypto coin statistics for specified coin

    Args:
        message (Message): Message to reply to
    """
    logger.info("Crypto command executed")
    reply = ""
    args = message.get_args().split()
    try:
        coin = Coin(symbol=args[0].upper())
        symbol = coin.symbol
        coin_stats_list = get_coin_stats(symbol=symbol)
        for coin_stats in coin_stats_list:
            explorers = "\n".join(coin_stats["explorers"])
            reply += (
                f"{coin_stats['token_name']} ({symbol})\n\n"
                f"Website\n{coin_stats['website']}\n\n"
                f"Explorers\n{explorers}\n\n"
            )

            for key in ("website", "explorers"):
                coin_stats.pop(key)
        dataframe = DataFrame(coin_stats_list)
        columns = {column: titleize(column) for column in dataframe.columns}
        dataframe = dataframe.rename(columns=columns)
        fig = fif.create_table(dataframe.rename(columns=columns))
        fig.update_layout(width=1000)

        await send_photo(
            chat_id=message.chat.id,
            caption=reply,
            photo=BufferedReader(
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))
            ),
        )
    except IndexError as e:
        logger.exception(e)
        reply = f"⚠️ Please provide a crypto code: \n{bold('/price')} {italic('COIN')}"
        await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)
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
    gas_price = ether_scan.get_gas_oracle()
    reply = (
        "ETH Gas Prices ⛽️\n"
        f"Slow: {gas_price['SafeGasPrice']}\n"
        f"Average: {gas_price['ProposeGasPrice']}\n"
        f"Fast: {gas_price['FastGasPrice']}\n"
    )
    await message.reply(text=reply)


async def send_price_address(message: Message) -> None:
    """Replies to command with coin stats for given crypto contract address

    Args:
        message (Message): Message to reply to
    """
    logger.info("Searching for coin by contract address")
    args = message.get_args().split()
    reply = ""
    try:
        address, platform, *_ = chain(args, ["", ""])
        coin = Coin(address=address, platform=platform)
        address = coin.address
        platform = coin.platform
        if platform == "BSC":
            user = User.from_orm(
                TelegramGroupMember.get_or_none(primary_key=message.from_user.id)
            )
            pancake_swap = PancakeSwap(
                address=user.bsc.address, key=user.bsc.private_key
            )
            token = pancake_swap.get_token(address=address)
            price = "${:,}".format(1 / pancake_swap.get_token_price(token=address))
            coin_stats = {"token_name": token.name, "price": price}
        else:

            coin_stats = get_coin_stats_by_address(address=address)
            explorers = "\n".join(coin_stats["explorers"])
            reply += (
                f"{coin_stats['token_name']} ({address})\n\n"
                f"Website\n{coin_stats.get('website')}\n\n"
                f"Explorers\n{explorers}\n\n"
            )

            for key in ("website", "explorers"):
                coin_stats.pop(key)
        dataframe = DataFrame(coin_stats, index=[0])
        columns = {column: titleize(column) for column in dataframe.columns}
        dataframe = dataframe.rename(columns=columns)
        fig = fif.create_table(dataframe.rename(columns=columns))
        fig.update_layout(width=1000)

        await send_photo(
            chat_id=message.chat.id,
            caption=reply,
            photo=BufferedReader(
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))
            ),
        )

    except IndexError as e:
        logger.exception(e)
        reply = (
            "⚠️ Please provide a crypto address: \n"
            f"{bold('/price')}_{bold('address')} {italic('ADDRESS')} {italic('PLATFORM')}"
        )
        await message.reply(text=reply)
    except ValueError as e:
        logger.exception(e)
        reply = "⚠️ Could not find coin"
        await message.reply(text=reply)


async def send_trending(message: Message) -> None:
    """Replies to command with trending crypto coins

    Args:
        message (Message): Message to reply to
    """
    logger.info("Retrieving trending addresses from CoinGecko")
    coin_gecko = CoinGecko()
    coin_market_cap = CoinMarketCap()
    coin_gecko_trending_coins = "\n".join(
        f"{coin['item']['name']} ({coin['item']['symbol']})"
        for coin in coin_gecko.get_trending_coins()
    )

    coin_market_cap_trending_coins = "\n".join(
        await coin_market_cap.get_trending_coins()
    )

    reply = (
        f"Trending 🔥\n\nCoinGecko\n\n{coin_gecko_trending_coins}\n\n"
        f"CoinMarketCap\n\n{coin_market_cap_trending_coins}"
    )

    await message.reply(text=reply)


async def send_price_alert(message: Message) -> None:
    """Replies to message with alert when coin passes expected mark price

    Args:
        message (Message): Message to reply to
    """
    logger.info("Setting a new price alert")
    args = message.get_args().split()

    try:
        alert = TokenAlert(
            symbol=args[0].upper(), sign=args[1], price=args[2].replace(",", "")
        )
        crypto = alert.symbol
        price = alert.price

        coin_stats = get_coin_stats(symbol=crypto)[0]

        crypto_alert = CryptoAlert.create(data=alert.dict())

        asyncio.create_task(price_alert_callback(alert=crypto_alert, delay=15))
        target_price = "${:,}".format(price.quantize(Decimal("0.01")))
        current_price = coin_stats["price"]
        reply = f"⏳ I will send you a message when the price of {crypto} reaches {target_price}\n"
        reply += f"The current price of {crypto} is {current_price}"
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
        coin_stats = get_coin_stats(symbol=crypto)[0]

        spot_price = Decimal(coin_stats["price"].replace("$", "").replace(",", ""))

        if sign == "<":
            if price >= spot_price:
                send = True
                dip = True
        elif price <= spot_price:
            send = True

        if send:

            price = "${:,}".format(price)
            spot_price = "${:,}".format(spot_price)

            if dip:
                response = f":( {crypto} has dipped below {price} and is currently at {spot_price}."
            else:
                response = f"👋 {crypto} has surpassed {price} and has just reached {spot_price}!"

            alert.remove()
            await send_message(channel_id=TELEGRAM_CHAT_ID, message=response)

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
                "https://www.coingecko.com/en/coins/recently_added", headers=HEADERS
        ) as response:
            df = read_html(await response.text(), flavor="bs4")[0]

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
        async with session.get(
                "https://coinmarketcap.com/new/", headers=HEADERS
        ) as response:
            df = read_html(await response.text(), flavor="bs4")[0]
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
        admin.user
        for admin in await bot.get_chat_administrators(chat_id=TELEGRAM_CHAT_ID)
    ]

    if user in administrators:
        logger.info("User %s is admin. Restarting KuCoin Bot", user.username)
        user = User.from_orm(TelegramGroupMember.get_or_none(primary_key=user.id))

        if (
                user.kucoin_api_key
                and user.kucoin_api_secret
                and user.kucoin_api_passphrase
        ):
            fernet = Fernet(FERNET_KEY)
            api_key = fernet.decrypt(user.kucoin_api_key.encode()).decode()
            api_secret = fernet.decrypt(user.kucoin_api_secret.encode()).decode()
            api_passphrase = fernet.decrypt(
                user.kucoin_api_passphrase.encode()
            ).decode()
            kucoin_api = KucoinApi(
                api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase
            )
            orders = kucoin_api.get_open_stop_order()

            for position in kucoin_api.get_all_position():
                if position["isOpen"]:
                    symbol = position["symbol"]
                    position_orders = [
                        order for order in orders if order["symbol"] == symbol
                    ]

                    for position_order in position_orders:
                        stop_price = position_order["stopPrice"]

                        if (
                                position_order["stopPriceType"] == "TP"
                                and position_order["stop"] == "up"
                        ):
                            take_profit = stop_price
                        else:
                            stop_loss = stop_price
                    symbol = symbol[:-1]
                    symbol = symbol.replace("XBTUSDT", "BTCUSDT")
                    entry = position["avgEntryPrice"]
                    mark_price = position["markPrice"]
                    unrealized_pnl = position["unrealisedPnl"]
                    side = (
                        "LONG"
                        if (entry < mark_price and unrealized_pnl > 0)
                           or (entry > mark_price and unrealized_pnl < 0)
                        else "SHORT"
                    )
                    active_orders.update(
                        {
                            symbol: {
                                "entry": entry,
                                "side": side,
                                "take_profit": take_profit,
                                "stop_loss": stop_loss,
                            }
                        }
                    )
            asyncio.create_task(kucoin_bot(), name=KUCOIN_TASK_NAME)
            reply = "Restarted KuCoin Bot 🤖"
        else:
            logger.info("User does not have a registered KuCoin account")
            reply = "⚠ Sorry, please register KuCoin account"
    else:
        logger.info("User is not admin")
        reply = "⚠ Sorry, this command can only be executed by an admin"
    await message.reply(text=reply)


async def send_buy(message: Message) -> None:
    """
    Command to buy coins in PancakeSwap
    Args:
        message (Message): Telegram chat message

    """
    logger.info("Started buy command")

    telegram_user = message.from_user
    args = message.get_args().split()

    try:
        user = User.from_orm(
            TelegramGroupMember.get_or_none(primary_key=telegram_user.id)
        )
        if user:
            trade = TradeCoin(address=args[0], amount=args[1], side=BUY)
            pancake_swap = PancakeSwap(
                address=user.bsc.address, key=user.bsc.private_key
            )
            reply = pancake_swap.swap_tokens(
                token=trade.address, amount_to_spend=trade.amount, side=trade.side
            )
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


async def send_sell(message: Message) -> None:
    """
    Command to sell coins in PancakeSwap
    Args:
        message (Message): Message to reply to

    """
    logger.info("Started sell command")
    telegram_user = message.from_user
    args = message.get_args().split()

    try:
        user = User.from_orm(
            TelegramGroupMember.get_or_none(primary_key=telegram_user.id)
        )
        if user:
            trade = TradeCoin(address=args[0], amount=0, side=SELL)
            pancake_swap = PancakeSwap(
                address=user.bsc.address, key=user.bsc.private_key
            )
            reply = pancake_swap.swap_tokens(token=trade.address, side=trade.side)
        else:
            reply = "⚠ Sorry, you must register prior to using this command."
    except IndexError as e:
        logger.exception(e)
        reply = "⚠️ Please provide a crypto token address and amount of BNB to spend: /sell_coin [ADDRESS]"
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
    reply = ""

    try:
        chart = Chart(ticker=args[0], time_frame=args[1])
        pair = chart.ticker.split("-")
        symbol = pair[0]
        base_coin = pair[1]
        time_frame = chart.time_frame

        coin_id = coin_gecko.get_coin_ids(symbol)[0]
        market = coin_gecko.coin_market_lookup(coin_id, time_frame, base_coin)

        logger.info("Creating chart layout")
        # Volume
        df_volume = DataFrame(market["total_volumes"], columns=["DateTime", "Volume"])
        df_volume["DateTime"] = to_datetime(df_volume["DateTime"], unit="ms")
        volume = go.Scatter(
            x=df_volume.get("DateTime"), y=df_volume.get("Volume"), name="Volume"
        )

        # Price
        df_price = DataFrame(market["prices"], columns=["DateTime", "Price"])
        df_price["DateTime"] = to_datetime(df_price["DateTime"], unit="ms")
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
            legend=dict(
                orientation="h", yanchor="top", xanchor="center", y=1.05, x=0.45
            ),
            shapes=[
                {
                    "type": "line",
                    "xref": "paper",
                    "yref": "y2",
                    "x0": 0,
                    "x1": 1,
                    "y0": market["prices"][-1][1],
                    "y1": market["prices"][-1][1],
                    "line": {"color": "rgb(50, 171, 96)", "width": 1, "dash": "dot"},
                }
            ],
        )

        fig = go.Figure(data=[price, volume], layout=layout)
        fig["layout"]["yaxis2"].update(tickformat=tick_format)
    except IndexError as e:
        logger.exception(e)
        reply = text(
            f"⚠️ Please provide a valid crypto symbol and amount of days: "
            f"\n{bold('/chart')} {italic('SYMBOL')} {italic('DAYS')}"
        )
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
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))
            ),
            parse_mode=ParseMode.MARKDOWN,
        )


async def send_candle_chart(message: Message):
    """Replies to command with coin candle chart for given crypto symbol and amount of time

    Args:
        message (Message): Message to reply to
    """
    logger.info("Executing candle chart command")
    args = message.get_args().split()
    reply = ""

    try:
        candle_chart = CandleChart(
            ticker=args[0], time_frame=args[1], resolution=args[2]
        )
        pair = candle_chart.ticker.split("-")
        symbol, base_coin = pair[0], pair[1]

        time_frame = candle_chart.time_frame
        resolution = candle_chart.resolution

        logger.info("Searching for coin historical data for candle chart")
        if resolution == "MINUTE":
            ohlcv = CryptoCompare().get_historical_ohlcv_minute(
                symbol, base_coin, time_frame
            )
        elif resolution == "HOUR":
            ohlcv = CryptoCompare().get_historical_ohlcv_hourly(
                symbol, base_coin, time_frame
            )
        else:
            ohlcv = CryptoCompare().get_historical_ohlcv_daily(
                symbol, base_coin, time_frame
            )
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
                    f" Data may not be as complete as CoinGecko or CMC"
                )
                await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)
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

            fig = fif.create_candlestick(
                open_, high, low, close, to_datetime(time_, unit="s")
            )

            fig["layout"]["yaxis"].update(
                tickformat=tick_format, tickprefix="   ", ticksuffix="  "
            )

            fig["layout"].update(
                title=dict(text=symbol, font=dict(size=26)),
                yaxis=dict(
                    title=dict(text=base_coin, font=dict(size=18)),
                ),
            )

            fig["layout"].update(
                shapes=[
                    {
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
                    }
                ]
            )

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
            f"{italic('NUMBER')} {italic('LETTER')}"
        )
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
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))
            ),
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
    logger.info("%s following KuCoin signal", username)
    user = User.from_orm(await TelegramGroupMember.get(id=user.id))
    if user.kucoin_api_key and user.kucoin_api_secret and user.kucoin_api_passphrase:
        fernet = Fernet(FERNET_KEY)
        api_key = fernet.decrypt(user.kucoin_api_key.encode()).decode()
        api_secret = fernet.decrypt(user.kucoin_api_secret.encode()).decode()
        api_passphrase = fernet.decrypt(user.kucoin_api_passphrase.encode()).decode()
        kucoin_api = KucoinApi(
            api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase
        )
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
            kucoin_api.create_market_order(
                symbol=symbol, side=side, size=int(size), lever=str(leverage)
            )
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

    user = User.from_orm(TelegramGroupMember.get_or_none(primary_key=user_id))
    platform = Platform(platform=message.get_args()).platform
    address, key = user.bsc.address, user.bsc.private_key
    if platform == "BSC":
        dex = PancakeSwap(address=address, key=key)
    # elif platform == "ETH":
    else:
        dex = UniSwap(address=address, key=key)

    account_holdings = await dex.get_account_token_holdings(
        address=dex.address
    )
    account_data_frame = DataFrame()
    for k in account_holdings.keys():
        coin = account_holdings[k]
        token = coin["address"]

        # Quantity in wei used to calculate price
        quantity = dex.get_token_balance(
            address=dex.address, token=token
        )
        if quantity > 0:
            try:
                token_price = dex.get_token_price(token=token)
                price = quantity / token_price

                # Quantity in correct format as seen in wallet
                quantity = dex.get_decimal_representation(
                    quantity=quantity, decimals=coin["decimals"]
                )
                # usd_amount = "${:,}".format(price.quantize(Decimal("0.01")))
                usd_amount = price.quantize(Decimal("0.01"))
                data_frame = DataFrame(
                    {"Symbol": [k], "Balance": [quantity], "USD": [usd_amount]}
                )
                account_data_frame = account_data_frame.append(
                    data_frame, ignore_index=True
                )
            except ContractLogicError as e:
                logger.exception(e)
    account_data_frame.sort_values(by=["USD"], inplace=True, ascending=False)
    account_data_frame["USD"] = account_data_frame["USD"].apply("${:,}".format)
    fig = fif.create_table(account_data_frame)
    fig.update_layout(
        autosize=True,
    )

    await send_photo(
        chat_id=user_id,
        caption="ETH Account Balance 💲",
        photo=BufferedReader(
            BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))
        ),
    )
    await message.reply(text="Replied privately 🤫")


async def send_spy(message: Message):
    logger.info("Executing spy command")
    counter = 0
    user_id = message.from_user.id
    user = User.from_orm(TelegramGroupMember.get_or_none(primary_key=user_id))
    bsc = BinanceSmartChain()
    args = message.get_args().split()
    account_data_frame = DataFrame()
    try:
        coin = Coin(address=args[0])
        account_holdings = await bsc.get_account_token_holdings(address=coin.address)
        pancake_swap = PancakeSwap(address=user.bsc.address, key=user.bsc.private_key)
        for k in account_holdings.keys():
            if counter > 5:
                break
            _coin = account_holdings[k]
            token = _coin["address"]

            # Quantity in wei used to calculate price
            quantity = bsc.get_token_balance(address=coin.address, token=token)
            if quantity > 0:
                try:
                    token_price = pancake_swap.get_token_price(token=token)
                    price = quantity / token_price

                    # Quantity in correct format as seen in wallet
                    quantity = pancake_swap.get_decimal_representation(
                        quantity=quantity, decimals=_coin["decimals"]
                    )
                    usd_amount = "${:,}".format(price.quantize(Decimal("0.01")))
                    data_frame = DataFrame(
                        {"Symbol": [k], "Balance": [quantity], "USD": [usd_amount]}
                    )
                    account_data_frame = account_data_frame.append(
                        data_frame, ignore_index=True
                    )
                    counter += 1
                except ContractLogicError as e:
                    logger.exception(e)

    except (IndexError, ValidationError) as e:
        logger.exception(e)
    fig = fif.create_table(account_data_frame)
    fig.update_layout(
        autosize=True,
    )
    await send_photo(
        chat_id=message.chat.id,
        caption="👀 Super Spy 👀",
        photo=BufferedReader(
            BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))
        ),
    )


async def send_snipe(message: Message):
    logger.info("Executing snipe command")
    args = message.get_args().split()
    address, amount, *_ = chain(args, ["", 0])
    trade = TradeCoin(address=address, amount=amount, side=BUY)

    user_id = message.from_user.id
    user = User.from_orm(TelegramGroupMember.get_or_none(primary_key=user_id))

    pancake_swap = PancakeSwap(address=user.bsc.address, key=user.bsc.private_key)
    asyncio.create_task(
        pancake_swap_sniper(
            chat_id=message.chat.id,
            token=trade.address,
            amount=trade.amount,
            pancake_swap=pancake_swap,
        )
    )
    await message.reply(
        text=f"🎯 Sniping {trade.address}...", parse_mode=ParseMode.MARKDOWN
    )


async def send_limit_swap(message: Message):
    logger.info("Executing limit swap command")
    args = message.get_args().split()
    trade_direction, address, target_price, bnb_amount, *_ = chain(
        args, ["", "", Decimal(0.0), Decimal(0.0)]
    )
    try:
        user_id = message.from_user.id
        # user = TelegramGroupMember.get_or_none(primary_key=user_id)
        limit_order = LimitOrder(
            trade_direction=trade_direction,
            address=address,
            target_price=target_price,
            bnb_amount=bnb_amount,
        )
        data = limit_order.dict()
        data.update({"telegram_group_member": user_id})

        order = Order.get_or_none(primary_key=Order.create(data=data).id)
        limit_order = LimitOrder.from_orm(order)
        asyncio.create_task(limit_order_executor(order=order))
        reply = f"Created limit order for {address}"
    except ValueError as e:
        logger.exception(e)
        reply = "Unable to create order"

    await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


async def send_active_orders(message: Message) -> None:
    """
    Replies with users active orders
    Args:
        message (Message): Message to reply to
    """
    logger.info("Executing active orders command")
    user_id = message.from_user.id
    orders = []
    user = User.from_orm(TelegramGroupMember.get_or_none(primary_key=user_id))
    dex = PancakeSwap(address=user.bsc.address, key=user.bsc.private_key)

    for order in Order.get_orders_by_member_id(telegram_group_member_id=user_id):
        token = dex.get_token(address=order.address)
        _order = LimitOrder.from_orm(order).dict(exclude={"address"})
        _order["telegram_group_member"] = user_id
        _order["token"] = token.name
        _order["symbol"] = token.symbol
        orders.append(_order)
    orders_dataframe = DataFrame(orders)

    if orders_dataframe.empty:
        await message.reply(text="No active orders", parse_mode=ParseMode.MARKDOWN)
    else:
        fig = fif.create_table(orders_dataframe)
        fig.update_layout(
            width=1000,
            autosize=True,
        )

        await message.reply_photo(
            photo=BufferedReader(
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))
            ),
            caption="Active Limit Orders",
        )


async def send_cancel_order(message: Message):
    logger.info("Executing delete order command")
    user_id = message.from_user.id
    reply = "Unable to cancel non-existent order"
    args = message.get_args()

    order_id = int(args)
    order = Order.get_or_none(primary_key=order_id)

    if order.telegram_group_member.id == user_id:
        reply = f"Cancelled order {order_id}"
        order.remove()

    await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)
