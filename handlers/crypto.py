import asyncio
import concurrent
import json
from time import time

import aiohttp
import pandas as pd
import requests
import io
import plotly.io as pio
import plotly.graph_objs as go

from aiogram.types import Message
from aiogram.types import ParseMode
from aiogram.utils.markdown import bold
from aiogram.utils.markdown import italic
from aiogram.utils.markdown import link
from aiogram.utils.markdown import text
from aiogram.utils.emoji import emojize
from cryptography.fernet import Fernet
from kucoin_futures.client import Trade
from web3 import Web3
from io import BytesIO
from pandas import DataFrame


from . import cg
from . import cmc
from . import crypto_cache
from . import eth
from . import logger
from app import bot
from bot import active_orders
from bot import KUCOIN_API_KEY
from bot import KUCOIN_API_PASSPHRASE
from bot import KUCOIN_API_SECRET
from bot import KUCOIN_TASK_NAME
from bot import TELEGRAM_CHAT_ID
from bot.kucoin_bot import kucoin_bot
from config import BINANCE_SMART_CHAIN_URL
from config import BSCSCAN_API_KEY
from config import BSCSCAN_API_URL
from config import FERNET_KEY
from handlers.base import send_message
from models import TelegramGroupMember







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
        reply = text(f"⚠️ Please provide a crypto address: \n{bold('/coin')}_{bold('address')} {italic('ADDRESS')}")
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
        logger.info("User is admin. Restarting KuCoin Bot")
        tasks = asyncio.all_tasks()
        [
            task.cancel() for task in tasks
            if task.get_name() == KUCOIN_TASK_NAME
        ]
        client = Trade(
            key=KUCOIN_API_KEY,
            secret=KUCOIN_API_SECRET,
            passphrase=KUCOIN_API_PASSPHRASE,
        )
        orders = [order for order in client.get_open_stop_order()["items"]]
        for position in client.get_all_position():
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
        logger.info("User is not admin")
        reply = "⚠ Sorry, this command can only be executed by an admin"
    await message.reply(text=reply)


def swap_tokens(token_to_buy, amount_to_spend, user):
    web3 = Web3(Web3.HTTPProvider(BINANCE_SMART_CHAIN_URL))
    contract_address = web3.toChecksumAddress(
        "0x10ED43C718714eb63d5aA57B78B54704E256024E"
    )  # Pancake Swap Contract Router

    if web3.isConnected():
        if user:
            fernet = Fernet(FERNET_KEY)
            user_address = web3.toChecksumAddress(user.bsc_address)
            # a = bytes(user.bsc_private_key)
            private_key = fernet.decrypt(user.bsc_private_key).decode()
            token_to_buy = web3.toChecksumAddress(token_to_buy)
            amount_to_spend = web3.toWei(float(amount_to_spend), "ether")
            max_slippage = 0.1
            url = BSCSCAN_API_URL.format(address=contract_address,
                                         api_key=BSCSCAN_API_KEY)

            # async with aiohttp.ClientSession() as session:
            #     async with session.get(url, headers=HEADERS) as response:
            #         data = await response.json()
            #         abi = json.loads(data['result'])
            data = requests.get(url).json()
            abi = json.loads(data["result"])
            contract = web3.eth.contract(address=contract_address, abi=abi)
            wbnb_address = contract.functions.WETH().call()
            nonce = web3.eth.getTransactionCount(user_address)
            deadline = int(time()) + 1000 * 60  # 1 minute deadline
            path = [wbnb_address, token_to_buy]
            amount_out_min = int(
                (1 - max_slippage) * contract.functions.getAmountsOut(
                    amount_to_spend, path).call()[-1])
            txn = contract.functions.swapExactETHForTokens(
                amount_out_min, path, user_address,
                deadline).buildTransaction({
                    "gas": 250000,
                    "gasPrice": web3.toWei("10", "gwei"),
                    "nonce": nonce,
                    "from": user_address,
                    "value": amount_to_spend,
                })
            sign_txn = web3.eth.account.signTransaction(
                txn, private_key=private_key)
            txn_hash = web3.toHex(
                web3.eth.sendRawTransaction(sign_txn.rawTransaction))

            txn_hash_url = f"https://bscscan.com/tx/{txn_hash}"
            reply = f"Transactions completed successfully. {link(title='View Transaction', url=txn_hash_url)}"
        else:
            reply = "⚠ Sorry, you must register prior to using this command."
    else:
        reply = "⚠ Sorry, I was unable to connect to the Binance Smart Chain. Try again later."
    return reply


async def send_buy_coin(message: Message):
    logger.info("Started buy coin command")

    telegram_user = message.from_user
    args = message.get_args().split()

    if len(args) != 2:
        reply = "⚠️ Please provide a crypto token address and amount of BNB to spend: /buy_coin [ADDRESS] [AMOUNT]"
    else:
        user = await TelegramGroupMember.filter(
            telegram_user_id=telegram_user.id).first()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        loop = asyncio.get_event_loop()
        reply = await loop.run_in_executor(executor, swap_tokens, args[0],
                                           args[1], user)

    await message.reply(text=reply)


def coingecko_coin_market_lookup(ids: str, time_frame: int) -> dict:
    """Coin lookup in CoinGecko API for Market Chart

    Args:
        ids (str): id of coin to lookup
        time_frame (int): Indicates number of days for data span

    Returns:
        dict: Data from CoinGecko API
    """
    logger.info(f"Looking up chart data for {ids} in CoinGecko API")

    return (cg.get_coin_market_chart_by_id(
                ids,
               "USD",
                time_frame))


def get_coin_id(symbol: str) -> dict:
    """Retrieves coinstats from connected services crypto services

    Args:
        symbol (str): Cryptocurrency symbol of coin to lookup

    Returns:
        str: coin id of the cryptocurrency
    """
    # Search Coingecko API first
    logger.info(f"Getting coin ID for {symbol}")

    if symbol in crypto_cache.keys():
        coin_id = crypto_cache[symbol]
            
    else:
        coin = [
            coin for coin in cg.get_coins_list()
            if coin["symbol"].upper() == symbol
        ][0]
        coin_id = coin["id"]
        crypto_cache[symbol] = coin_id
    
    return coin_id



async def send_chart(message: Message):
    """Replies to command with coin chart for given crypto symbol and amount of days

    Args:
        message (Message): Message to reply to
    """
    logger.info("Searching for coin market data for chart")
    args = message.get_args().split()
    reply = ''

    if len(args) != 2:
        reply = text(f"⚠️ Please provide a valid crypto symbol and amount of days: \n{bold('/chart')} {italic('SYMBOL')} {italic('DAYS')}")
    else:
        symbol = args[0].upper()    
        time_frame = args[1] 
        coin_id = get_coin_id(symbol)
        market = coingecko_coin_market_lookup(coin_id, time_frame)


        logger.info("Creating chart layout")
        # Volume
        df_volume = DataFrame(market["total_volumes"], columns=["DateTime", "Volume"])
        df_volume["DateTime"] = pd.to_datetime(df_volume["DateTime"], unit="ms")
        volume = go.Scatter(
            x=df_volume.get("DateTime"),
            y=df_volume.get("Volume"),
            name="Volume"
        )

        # Price
        df_price = DataFrame(market["prices"], columns=["DateTime", "Price"])
        df_price["DateTime"] = pd.to_datetime(df_price["DateTime"], unit="ms")
        price = go.Scatter(
            x=df_price.get("DateTime"),
            y=df_price.get("Price"),
            yaxis="y2",
            name="Price",
            line=dict(
                color=("rgb(22, 96, 167)"),
                width=2
            )
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
            paper_bgcolor='rgb(233,233,233)',
            plot_bgcolor='rgb(233,233,233)',
            autosize=False,
            width=800,
            height=600,
            margin=go.layout.Margin(
                l=margin_l,
                r=50,
                b=85,
                t=100,
                pad=4
            ),
            yaxis=dict(
                domain=[0, 0.20]
            ),
            yaxis2=dict(
                title=dict(
                    text='USD',
                    font=dict(
                        size=18
                    )
                ),                domain=[0.25, 1],
                tickprefix="   ",
                ticksuffix=f"  "
            ),
            title=dict(
                text=symbol,
                font=dict(
                    size=26
                )
            ),
            legend=dict(
                orientation="h",
                yanchor="top",
                xanchor="center",
                y=1.05,
                x=0.45
            ),
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
                }
            }],
        )

        
        fig = go.Figure(data=[price, volume], layout=layout)
        fig["layout"]["yaxis2"].update(tickformat=tickformat)

    if reply:
        await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)
    else:
        logger.info("Exporting chart as image")
        await message.reply_photo(
            photo=io.BufferedReader(BytesIO(pio.to_image(fig, format='jpeg', engine='kaleido'))),
            parse_mode=ParseMode.MARKDOWN)

