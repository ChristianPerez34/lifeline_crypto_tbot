import asyncio
import random
import time
from decimal import Decimal
from io import BufferedReader, BytesIO
from itertools import chain
from typing import Dict
from urllib.parse import urlparse

import aiohttp
import dateutil.parser as dau
import plotly.figure_factory as fif
import plotly.graph_objs as go
import plotly.io as pio
from aiocoingecko.errors import HTTPException
from aiogram.types import (
    CallbackQuery,
    Message,
    ParseMode,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.emoji import emojize
from aiogram.utils.markdown import bold, italic, text
from coinmarketcapapi import CoinMarketCapAPIError
from copra.rest.client import APIRequestError
from cryptography.fernet import Fernet
from inflection import titleize, humanize
from pandas import DataFrame, read_html, to_datetime
from pydantic.error_wrappers import ValidationError
from requests.exceptions import RequestException, HTTPError
from web3 import Web3
from web3.exceptions import ContractLogicError

from api.bsc import PancakeSwap
from api.coinbase import CoinBaseApi
from api.coingecko import CoinGecko
from api.coinmarketcap import CoinMarketCap
from api.coinpaprika import CoinPaprika
from api.cryptocompare import CryptoCompare
from api.eth import UniSwap
from api.kucoin import KucoinApi
from api.matic import QuickSwap
from app import bot, logger, chart_cb, alert_cb, price_cb
from bot import active_orders
from bot.bsc_order import limit_order_executor
from bot.bsc_sniper import pancake_swap_sniper
from bot.kucoin_bot import kucoin_bot
from config import BUY, FERNET_KEY, HEADERS, KUCOIN_TASK_NAME, SELL, TELEGRAM_CHAT_ID
from handlers.base import send_message, send_photo, is_admin_user
from models import CryptoAlert, TelegramGroupMember, Order, MonthlySubmission
from schemas import (
    CandleChart,
    Chart,
    Coin,
    TokenAlert,
    TradeCoin,
    User,
    LimitOrder,
    Platform,
    CoinbaseOrder,
    TokenSubmission,
)
from utils import all_same
from . import gas_tracker


def get_coin_explorers(platforms: dict, links: dict) -> list:
    """
    Locates token explorers and stores them in a list
    Args:
        platforms (dict): Chains where token is available
        links (dict): Blockchain sites

    Returns (list): List of all available explorers

    """
    explorers = [
        f"[{urlparse(link).hostname.split('.')[0]}]({link})"
        for link in links["blockchain_site"]
        if link
    ]

    for network, address in platforms.items():
        explorer = ""

        if "ethereum" in network:
            address = Web3.toChecksumAddress(address)
            explorer = f"[etherscan](https://etherscan.io/token/{address})"
        elif "binance" in network:
            address = Web3.toChecksumAddress(address)
            explorer = f"[bscscan](https://bscscan.com/token/{address})"
        elif "polygon" in network:
            address = Web3.toChecksumAddress(address)
            explorer = f"[polygonscan](https://polygonscan.com/token/{address})"
        elif "solana" in network:
            explorer = (
                f"[explorer.solana](https://explorer.solana.com/address/{address})"
            )

        if explorer and explorer not in explorers:
            explorers.append(explorer)
    return explorers


async def get_coin_ids(symbol: str) -> list:
    """
    Retrieves coin IDs from supported market aggregators
    Args:
        symbol: Token symbol

    Returns: List of matching symbols

    """
    coin_gecko = CoinGecko()
    coin_market_cap = CoinMarketCap()
    try:
        coin_ids = await coin_gecko.get_coin_ids(symbol=symbol)
    except (IndexError, HTTPError):
        coin_ids = coin_market_cap.get_coin_ids(symbol=symbol)
    return coin_ids


async def get_coin_stats(coin_id: str) -> dict:
    """Retrieves coin stats from connected services crypto services

    Args:
        coin_id (str): ID of coin to lookup in cryptocurrency market aggregators

    Returns:
        dict: Cryptocurrency coin statistics
    """
    # Search CoinGecko API first
    logger.info("Getting coin stats for %s", coin_id)
    coin_gecko = CoinGecko()
    coin_market_cap = CoinMarketCap()
    coin_stats = {}
    try:
        data = await coin_gecko.coin_lookup(ids=coin_id)

        market_data = data["market_data"]
        links = data["links"]
        platforms = data["platforms"]

        explorers = get_coin_explorers(platforms=platforms, links=links)
        price = "${:,}".format(float(market_data["current_price"]["usd"]))
        all_time_high = "${:,}".format(float(market_data["ath"]["usd"]))
        market_cap = "${:,}".format(float(market_data["market_cap"]["usd"]))
        volume = "${:,}".format(float(market_data["total_volume"]["usd"]))

        percent_change_24h = market_data["price_change_percentage_24h"]
        percent_change_7d = market_data["price_change_percentage_7d"]
        percent_change_30d = market_data["price_change_percentage_30d"]
        percent_change_ath = market_data["ath_change_percentage"]["usd"]
        market_cap_rank = market_data["market_cap_rank"]

        coin_stats.update(
            {
                "name": data["name"],
                "symbol": data["symbol"].upper(),
                "website": links["homepage"][0],
                "explorers": explorers,
                "price": price,
                "ath": all_time_high,
                "market_cap_rank": market_cap_rank,
                "market_cap": market_cap,
                "volume": volume,
                "percent_change_24h": percent_change_24h,
                "percent_change_7d": percent_change_7d,
                "percent_change_30d": percent_change_30d,
                "percent_change_ath": percent_change_ath,
            }
        )
    except (IndexError, HTTPError, HTTPException):
        logger.info(
            "%s not found in CoinGecko. Initiated lookup on CoinMarketCap.", coin_id
        )
        ids = coin_id[0]
        coin_lookup = coin_market_cap.coin_lookup(ids=ids)
        meta_data = coin_market_cap.get_coin_metadata(ids=ids)[ids]
        data = coin_lookup[ids]
        urls = meta_data["urls"]
        quote = data["quote"]["USD"]
        explorers = [
            f"[{urlparse(link).hostname.split('.')[0]}]({link})"
            for link in urls["explorer"]
            if link
        ]

        for key in quote:
            if quote[key] is None:
                quote[key] = 0
        price = "${:,}".format(quote["price"])
        market_cap = "${:,}".format(quote["market_cap"])
        volume = "${:,}".format(quote["volume_24h"])
        percent_change_24h = quote["percent_change_24h"]
        percent_change_7d = quote["percent_change_7d"]
        percent_change_30d = quote["percent_change_30d"]

        coin_stats.update(
            {
                "name": data["name"],
                "symbol": data["symbol"],
                "website": urls["website"][0],
                "explorers": explorers,
                "price": price,
                "market_cap_rank": data["cmc_rank"],
                "market_cap": market_cap,
                "volume": volume,
                "percent_change_24h": percent_change_24h,
                "percent_change_7d": percent_change_7d,
                "percent_change_30d": percent_change_30d,
            }
        )
    return coin_stats


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
    args = message.get_args().split()

    try:
        coin = Coin(symbol=args[0].upper())
        symbol = coin.symbol
        coin_ids = await get_coin_ids(symbol=symbol)
        coin_ids_len = len(coin_ids)

        if coin_ids_len == 1:
            coin_stats = await get_coin_stats(coin_id=coin_ids[0])
            percent_change_24h = coin_stats["percent_change_24h"]
            percent_change_7d = coin_stats["percent_change_7d"]
            percent_change_30d = coin_stats["percent_change_30d"]

            if "ath" in coin_stats:
                percent_change_ath = coin_stats["percent_change_ath"]
                reply = (
                    f"💲 {coin_stats['name']} ({coin_stats['symbol']})\n"
                    f"💻 Website: {coin_stats['website']}\n"
                    f"🔍 Explorers: {', '.join(coin_stats['explorers'])}\n\n"
                    f"💵 Price: {coin_stats['price']}\n"
                    f"🔜 ATH: {coin_stats['ath']}\n\n"
                    f"🏅 Market Cap Rank: {coin_stats['market_cap_rank']}\n"
                    f"🏦 Market Cap: {coin_stats['market_cap']}\n"
                    f"💰 Volume: {coin_stats['volume']}\n\n"
                    f"{'📈' if percent_change_24h > 0 else '📉'} 24H Change: {percent_change_24h}%\n"
                    f"{'📈' if percent_change_7d > 0 else '📉'} 7D Change: {percent_change_7d}%\n"
                    f"{'📈' if percent_change_30d > 0 else '📉'} 30D Change: {percent_change_30d}%\n"
                    f"{'📈' if percent_change_ath > 0 else '📉'} ATH Change: {percent_change_ath}%\n"
                )
            else:
                reply = (
                    f"💲 {coin_stats['name']} ({coin_stats['symbol']})\n"
                    f"💻 Website: {coin_stats['website']}\n"
                    f"🔍 Explorers: {', '.join(coin_stats['explorers'])}\n\n"
                    f"💵 Price: {coin_stats['price']}\n\n"
                    f"🏅 Market Cap Rank: {coin_stats['market_cap_rank']}\n"
                    f"🏦 Market Cap: {coin_stats['market_cap']}\n"
                    f"💰 Volume: {coin_stats['volume']}\n\n"
                    f"{'📈' if percent_change_24h > 0 else '📉'} 24H Change: {percent_change_24h}%\n"
                    f"{'📈' if percent_change_7d > 0 else '📉'} 7D Change: {percent_change_7d}%\n"
                    f"{'📈' if percent_change_30d > 0 else '📉'} 30D Change: {percent_change_30d}%\n"
                )
            await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)
        elif coin_ids_len > 1:
            keyboard_markup = InlineKeyboardMarkup()
            for coin_id in coin_ids:
                if isinstance(coin_id, tuple):
                    ids, token_name = coin_id
                else:
                    ids = token_name = coin_id
                keyboard_markup.row(
                    InlineKeyboardButton(
                        token_name,
                        callback_data=price_cb.new(command="price", coin_id=ids),
                    )
                )

            await message.reply(
                text="Choose token to display statistics",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard_markup,
            )
        else:
            await message.reply(
                text="❌ Token data not found in CoinMarketCap/CoinGecko",
                parse_mode=ParseMode.MARKDOWN,
            )
    except IndexError as error:
        logger.exception(error)
        reply = f"⚠️ Please provide a crypto code: \n{bold('/price')} {italic('COIN')}"
        await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)
    except ValidationError as error:
        logger.exception(error)
        error_message = error.args[0][0].exc
        reply = f"⚠️ {error_message}"
        await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


async def send_gas(message: Message) -> None:
    """Replies to command with eth gas fees

    Args:
        message (Message): Message to reply to
    """
    logger.info("ETH gas price command executed")
    gas_price = await gas_tracker.get_gasprices()
    reply = (
        "ETH Gas Prices ⛽️\n"
        f"Slow: {Web3.fromWei(gas_price['regular'], 'gwei')}\n"
        f"Average: {Web3.fromWei(gas_price['fast'], 'gwei')}\n"
        f"Fast: {Web3.fromWei(gas_price['fastest'], 'gwei')}\n"
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
        address, network, *_ = chain(args, ["", ""])
        coin = Coin(address=address, network=network)
        address = coin.address
        network = coin.network
        if network == "BSC":
            user = User.from_orm(
                TelegramGroupMember.get_or_none(primary_key=message.from_user.id)
            )
            pancake_swap = PancakeSwap(
                address=user.bsc.address, key=user.bsc.private_key  # type: ignore
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
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))  # type: ignore
            ),
        )

    except IndexError as error:
        logger.exception(error)
        reply = (
            "⚠️ Please provide a crypto address: \n"
            f"{bold('/price')}_{bold('address')} {italic('ADDRESS')} {italic('NETWORK')}"
        )
        await message.reply(text=reply)
    except ValueError as error:
        logger.exception(error)
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
        for coin in await coin_gecko.get_trending_coins()
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

        coin_ids = await get_coin_ids(symbol=crypto)

        if len(coin_ids) == 1:
            coin_id = coin_ids[0][0] if isinstance(coin_ids[0], tuple) else coin_ids[0]
            stats: dict = await get_coin_stats(coin_id=coin_id)
            alert.coin_id = coin_id
            CryptoAlert.create(data=alert.dict())
            target_price = "${:,}".format(price.quantize(Decimal("0.01")))

            current_price = stats["price"]
            reply = f"⏳ I will send you a message when the price of {crypto} reaches {target_price}\n"
            reply += f"The current price of {crypto} is {current_price}"
            await message.reply(text=reply)
        else:
            keyboard_markup = InlineKeyboardMarkup()
            for coin_id in coin_ids:
                if isinstance(coin_id, tuple):
                    ids, token_name = coin_id
                else:
                    ids = token_name = coin_id
                token_name = coin_id[1] if isinstance(coin_id, tuple) else coin_id
                keyboard_markup.row(
                    InlineKeyboardButton(
                        token_name,
                        callback_data=alert_cb.new(
                            alert_type="price",
                            symbol=crypto,
                            sign=alert.sign,
                            target_price=price,
                            coin_id=ids,
                        ),
                    )
                )

            await message.reply(
                text="Choose token to create alert",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard_markup,
            )
    except IndexError as error:
        logger.exception(error)
        reply = "⚠️ Please provide a crypto code and a price value: /alert [COIN] [<,>] [PRICE]"
        await message.reply(text=reply)
    except ValidationError as error:
        logger.exception(error)
        error_message = error.args[0][0].exc
        reply = f"⚠️ {error_message}"
        await message.reply(text=reply)


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

    try:
        network, address, amount = message.get_args().split()
        user = User.from_orm(
            TelegramGroupMember.get_or_none(primary_key=telegram_user.id)
        )
        if user:
            trade = TradeCoin(network=network, address=address, amount=amount, side=BUY)
            network = trade.network

            if network == "BSC":
                dex = PancakeSwap(address=user.bsc.address, key=user.bsc.private_key)  # type: ignore
            elif network == "ETH":
                dex = UniSwap(address=user.eth.address, key=user.eth.private_key)  # type: ignore
            else:
                dex = QuickSwap(address=user.matic.address, key=user.matic.private_key)  # type: ignore

            reply = dex.swap_tokens(
                token=trade.address, amount_to_spend=trade.amount, side=trade.side
            )
        else:
            reply = "⚠ Sorry, you must register prior to using this command."
    except IndexError as error:
        logger.exception(error)
        reply = "⚠️ Please provide a crypto token address and amount of BNB to spend: /buy_coin [ADDRESS] [AMOUNT]"
    except ValidationError as error:
        logger.exception(error)
        error_message = error.args[0][0].exc
        reply = f"⚠️ {error_message}"
    except ValueError as error:
        logger.exception(error)
        reply = "⚠ Please provide network, address & amount to spend. Ex: /buy bsc 0x000000000000000000 0.01"

    await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


async def send_sell(message: Message) -> None:
    """
    Command to sell coins in PancakeSwap
    Args:
        message (Message): Message to reply to

    """
    logger.info("Started sell command")
    telegram_user = message.from_user

    try:
        network, address = message.get_args().split()
        user = User.from_orm(
            TelegramGroupMember.get_or_none(primary_key=telegram_user.id)
        )
        if user:
            trade = TradeCoin(network=network, address=address, amount=0, side=SELL)
            network = trade.network

            if network == "BSC":
                dex = PancakeSwap(address=user.bsc.address, key=user.bsc.private_key)  # type: ignore
            elif network == "ETH":
                dex = UniSwap(address=user.eth.address, key=user.eth.private_key)  # type: ignore
            else:
                dex = QuickSwap(address=user.matic.address, key=user.matic.private_key)  # type: ignore

            reply = await dex.swap_tokens(
                token=trade.address, amount_to_spend=trade.amount, side=trade.side
            )
        else:
            reply = "⚠ Sorry, you must register prior to using this command."
    except IndexError as error:
        logger.exception(error)
        reply = "⚠️ Please provide a crypto token address and amount of BNB to spend: /sell_coin [ADDRESS]"
    except ValidationError as error:
        logger.exception(error)
        error_message = error.args[0][0].exc
        reply = f"⚠️ {error_message}"
    except ValueError as error:
        logger.exception(error)
        reply = "⚠ Please provide network, address & amount to spend. Ex: /sell bsc 0x000000000000000000"

    await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


async def generate_line_chart(
    coin_gecko: CoinGecko, coin_id: str, symbol: str, time_frame: int, base_coin: str
) -> go.Figure:
    logger.info("Creating line chart layout")
    market = await coin_gecko.coin_market_lookup(coin_id, time_frame, base_coin)

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
        legend=dict(orientation="h", yanchor="top", xanchor="center", y=1.05, x=0.45),
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
    return fig


async def send_chart(message: Message):
    """Replies to command with coin chart for given crypto symbol and amount of days

    Args:
        message (Message): Message to reply to
    """
    logger.info("Searching for coin market data for chart")
    coin_gecko = CoinGecko()
    coin_market_cap = CoinMarketCap()
    args = message.get_args().split()
    reply = ""

    try:
        chart = Chart(ticker=args[0], time_frame=args[1])
        pair = chart.ticker.split("-")
        symbol, base_coin = pair
        time_frame = chart.time_frame

        coin_ids = await coin_gecko.get_coin_ids(
            symbol
        ) or coin_market_cap.get_coin_ids(symbol=symbol)
        if len(coin_ids) == 1:
            fig = await generate_line_chart(
                coin_gecko=coin_gecko,
                coin_id=coin_ids[0],
                symbol=symbol,
                time_frame=time_frame,
                base_coin=base_coin,
            )

            logger.info("Exporting line chart as image")
            await message.reply_photo(
                photo=BufferedReader(
                    BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))  # type: ignore
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            keyboard_markup = InlineKeyboardMarkup()
            for coin_id in coin_ids:
                keyboard_markup.row(
                    InlineKeyboardButton(
                        humanize(coin_id),
                        callback_data=chart_cb.new(
                            chart_type="line",
                            coin_id=coin_id,
                            symbol=symbol,
                            time_frame=time_frame,
                            base_coin=base_coin,
                        ),
                    )
                )

            await message.reply(
                text="Choose token to display chart",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard_markup,
            )
    except IndexError as error:
        logger.exception(error)
        reply = text(
            f"⚠️ Please provide a valid crypto symbol and amount of days: "
            f"\n{bold('/chart')} {italic('SYMBOL')} {italic('DAYS')}"
        )
    except ValidationError as error:
        logger.exception(error)
        error_message = error.args[0][0].exc
        reply = f"⚠️ {error_message}"
    except CoinMarketCapAPIError as error:
        logger.exception(error)
        reply = "Coin data not found in CoinGecko/CoinMarketCap"

    if reply:
        await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)


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
        symbol, base_coin = pair

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
                    if close["symbol"] == symbol:  # type: ignore

                        # Current datetime in seconds
                        t_now = time.time()
                        # Convert chart time span to seconds
                        time_frame = int(time_frame) * 24 * 60 * 60
                        # Start datetime for chart in seconds
                        t_start = t_now - int(time_frame)

                        ohlcv = CoinPaprika().get_historical_ohlc(
                            close["id"],  # type: ignore
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
    except IndexError as error:
        logger.exception(error)
        reply = text(
            f"⚠️ Please provide a valid crypto symbol and time followed by desired timeframe letter:\n"
            f" m - Minute\n h - Hour\n d - Day\n \n{bold('/candle')} {italic('SYMBOL')} "
            f"{italic('NUMBER')} {italic('LETTER')}"
        )
    except ValidationError as error:
        logger.exception(error)
        error_message = error.args[0][0].exc
        reply = f"⚠️ {error_message}"

    if reply:
        await message.reply(text=emojize(reply), parse_mode=ParseMode.MARKDOWN)
    else:
        logger.info("Exporting chart as image")
        await message.reply_photo(
            photo=BufferedReader(
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))  # type: ignore
            ),
            parse_mode=ParseMode.MARKDOWN,
        )


async def chart_inline_query_handler(
    query: CallbackQuery, callback_data: Dict[str, str]
):
    await query.message.delete_reply_markup()
    await query.answer("Generating chart")
    chart_type = callback_data["chart_type"]

    if chart_type == "line":
        coin_gecko = CoinGecko()
        coin_id = callback_data["coin_id"]
        symbol = callback_data["symbol"]
        time_frame = int(callback_data["time_frame"])
        base_coin = callback_data["base_coin"]
        fig = await generate_line_chart(
            coin_gecko=coin_gecko,
            coin_id=coin_id,
            symbol=symbol,
            time_frame=time_frame,
            base_coin=base_coin,
        )

        logger.info("Exporting line chart as image")
        await send_photo(
            chat_id=TELEGRAM_CHAT_ID,
            caption=coin_id,
            photo=BufferedReader(
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))  # type: ignore
            ),
        )


async def alert_inline_query_handler(
    query: CallbackQuery, callback_data: Dict[str, str]
):
    await query.message.delete_reply_markup()
    await query.answer("Creating alert!")

    alert = TokenAlert(
        symbol=callback_data["symbol"],
        sign=callback_data["sign"],
        price=callback_data["target_price"],
        coin_id=callback_data["coin_id"],
    )
    CryptoAlert.create(data=alert.dict())
    target_price = "${:,}".format(alert.price.quantize(Decimal("0.01")))
    reply = f"⏳ I will send you a message when the price of {alert.symbol} reaches {target_price}\n"
    await query.message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


async def price_inline_query_handler(
    query: CallbackQuery, callback_data: Dict[str, str]
):
    await query.message.delete_reply_markup()
    await query.answer("Retrieving price data")

    coin_id = callback_data["coin_id"]
    coin_stats = await get_coin_stats(coin_id=coin_id)

    percent_change_24h = coin_stats["percent_change_24h"]
    percent_change_7d = coin_stats["percent_change_7d"]
    percent_change_30d = coin_stats["percent_change_30d"]

    if "ath" in coin_stats:
        percent_change_ath = coin_stats["percent_change_ath"]
        reply = (
            f"💲 {coin_stats['name']} ({coin_stats['symbol']})\n"
            f"💻 Website: {coin_stats['website']}\n"
            f"🔍 Explorers: {', '.join(coin_stats['explorers'])}\n\n"
            f"💵 Price: {coin_stats['price']}\n"
            f"🔜 ATH: {coin_stats['ath']}\n\n"
            f"🏅 Market Cap Rank: {coin_stats['market_cap_rank']}\n"
            f"🏦 Market Cap: {coin_stats['market_cap']}\n"
            f"💰 Volume: {coin_stats['volume']}\n\n"
            f"{'📈' if percent_change_24h > 0 else '📉'} 24H Change: {percent_change_24h}%\n"
            f"{'📈' if percent_change_7d > 0 else '📉'} 7D Change: {percent_change_7d}%\n"
            f"{'📈' if percent_change_30d > 0 else '📉'} 30D Change: {percent_change_30d}%\n"
            f"{'📈' if percent_change_ath > 0 else '📉'} 30D Change: {percent_change_ath}%\n"
        )
    else:
        reply = (
            f"💲 {coin_stats['name']} ({coin_stats['symbol']})\n"
            f"💻 Website: {coin_stats['website']}\n"
            f"🔍 Explorers: {', '.join(coin_stats['explorers'])}\n\n"
            f"💵 Price: {coin_stats['price']}\n\n"
            f"🏅 Market Cap Rank: {coin_stats['market_cap_rank']}\n"
            f"🏦 Market Cap: {coin_stats['market_cap']}\n"
            f"💰 Volume: {coin_stats['volume']}\n\n"
            f"{'📈' if percent_change_24h > 0 else '📉'} 24H Change: {percent_change_24h}%\n"
            f"{'📈' if percent_change_7d > 0 else '📉'} 7D Change: {percent_change_7d}%\n"
            f"{'📈' if percent_change_30d > 0 else '📉'} 30D Change: {percent_change_30d}%\n"
        )
    await query.message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


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
        except RequestException as error:
            logger.exception(error)
            reply = "⚠️ Unable to follow signal"

    else:
        reply = "⚠️ Please register KuCoin account to follow signals"
    await send_message(channel_id=query.message.chat.id, message=reply)


async def send_balance(message: Message):
    logger.info("Retrieving account balance")
    user_id = message.from_user.id

    user = User.from_orm(TelegramGroupMember.get_or_none(primary_key=user_id))
    network = Platform(network=message.get_args()).network

    if network == "BSC":
        exchange = PancakeSwap(address=user.bsc.address, key=user.bsc.private_key)  # type: ignore
    elif network == "ETH":
        exchange = UniSwap(address=user.eth.address, key=user.eth.private_key)  # type: ignore
    elif network == "MATIC":
        exchange = QuickSwap(address=user.matic.address, key=user.matic.private_key)  # type: ignore
    else:
        coinbase = user.coinbase
        exchange = CoinBaseApi(
            api_key=coinbase.api_key,
            api_secret=coinbase.api_secret,
            api_passphrase=coinbase.api_passphrase,
        )

    logger.info("Creating Account balance dataframe for user %d", user_id)
    account_holdings = await exchange.get_account_token_holdings()

    account_holdings.sort_values(by=["USD"], inplace=True, ascending=False)
    account_holdings["USD"] = account_holdings["USD"].apply("${:,}".format)
    fig = fif.create_table(account_holdings)
    fig.update_layout(
        autosize=True,
    )

    logger.info("Account balance data sent")
    await send_photo(
        chat_id=user_id,
        caption=f"{network} Account Balance 💲",
        photo=BufferedReader(
            BytesIO(pio.to_image(fig, format="png", engine="kaleido"))  # type: ignore
        ),
    )
    await message.reply(text="Replied privately 🤫")


async def send_spy(message: Message):
    logger.info("Executing spy command")
    counter = 0
    user_id = message.from_user.id
    user = User.from_orm(TelegramGroupMember.get_or_none(primary_key=user_id))
    account_data_frame = DataFrame()
    try:
        network, address = message.get_args().split()
        coin = Coin(address=address, network=network)

        if coin.network == "BSC":
            dex = PancakeSwap(address=user.bsc.address, key=user.bsc.private_key)  # type: ignore
        elif coin.network == "ETH":
            dex = UniSwap(address=user.eth.address, key=user.eth.private_key)  # type: ignore
        else:
            dex = QuickSwap(address=user.matic.address, key=user.matic.private_key)  # type: ignore
        account_holdings = await dex.get_account_token_holdings(address=coin.address)

        for k in account_holdings.keys():
            if counter > 5:
                break
            _coin = account_holdings[k]
            token = _coin["address"]

            # Quantity in wei used to calculate price
            quantity = dex.get_token_balance(address=coin.address, token=token)
            if quantity > 0:
                try:
                    token_price = dex.get_token_price(token=token)
                    price = quantity / token_price

                    # Quantity in correct format as seen in wallet
                    quantity = dex.get_decimal_representation(
                        quantity=quantity, decimals=_coin["decimals"]
                    )
                    usd_amount = price.quantize(Decimal("0.01"))
                    data_frame = DataFrame(
                        {"Symbol": [k], "Balance": [quantity], "USD": [usd_amount]}
                    )
                    account_data_frame = account_data_frame.append(
                        data_frame, ignore_index=True
                    )
                    counter += 1
                except ContractLogicError as error:
                    logger.exception(error)

    except (IndexError, ValidationError) as error:
        logger.exception(error)
    account_data_frame.sort_values(by=["USD"], inplace=True, ascending=False)
    account_data_frame["USD"] = account_data_frame["USD"].apply("${:,}".format)
    fig = fif.create_table(account_data_frame)
    fig.update_layout(
        autosize=True,
    )
    await send_photo(
        chat_id=message.chat.id,
        caption="👀 Super Spy 👀",
        photo=BufferedReader(
            BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))  # type: ignore
        ),
    )


async def send_snipe(message: Message):
    logger.info("Executing snipe command")
    args = message.get_args().split()
    address, amount, *_ = chain(args, ["", 0])
    trade = TradeCoin(address=address, amount=amount, side=BUY)

    user_id = message.from_user.id
    user = User.from_orm(TelegramGroupMember.get_or_none(primary_key=user_id))

    pancake_swap = PancakeSwap(address=user.bsc.address, key=user.bsc.private_key)  # type: ignore
    asyncio.create_task(
        pancake_swap_sniper(
            chat_id=message.chat.id,
            token=trade.address,  # type: ignore
            amount=trade.amount,
            pancake_swap=pancake_swap,
        )
    )
    await message.reply(
        text=f"🎯 Sniping {trade.address}...", parse_mode=ParseMode.MARKDOWN  # type: ignore
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
    except ValueError as error:
        logger.exception(error)
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
    dex = PancakeSwap(address=user.bsc.address, key=user.bsc.private_key)  # type: ignore

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
                BytesIO(pio.to_image(fig, format="jpeg", engine="kaleido"))  # type: ignore
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


async def send_coinbase(message: Message):
    """
    Replies with coinbase order results
    Args:
        message: Message to reply to

    """
    logger.info("Executing coinbase command")
    user_id = message.from_user.id
    args = message.get_args().split()
    order_type, trade_direction, symbol, amount, limit_price = args + [""] * (
        5 - len(args)
    )
    user = User.from_orm(TelegramGroupMember.get_or_none(primary_key=user_id))
    amount = float(amount) if amount else 0.0
    limit_price = float(limit_price) if limit_price else 0.0
    order = CoinbaseOrder(
        order_type=order_type,
        trade_direction=trade_direction,
        symbol=symbol,
        amount=amount,
        limit_price=limit_price,
    )
    coinbase = CoinBaseApi(
        api_key=user.coinbase.api_key,
        api_secret=user.coinbase.api_secret,
        api_passphrase=user.coinbase.api_passphrase,
    )
    try:
        await coinbase.trade(
            order_type=order.order_type,
            trade_direction=order.trade_direction.lower(),
            symbol=order.symbol,
            amount=order.amount,
            limit_price=order.limit_price,
        )

        reply = f"🙌 {humanize(order.order_type)} order executed successfully"
    except IndexError:
        reply = f"😞 Provided symbol ({bold(order.symbol)}) is not available for trading on CoinBase"
    except APIRequestError as error:
        reply = f"😔 {humanize(str(error).split('[', maxsplit=1)[0])}"

    await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


async def send_submit(message: Message):
    """
    Replies whether crypto token submission was successful
    Args:
        message: Message to reply to

    """
    logger.info("Executing submit command")
    args = message.get_args().split()
    symbol = args.pop(-1)
    token_name = " ".join(args)

    try:
        token_submission = TokenSubmission(token_name=token_name, symbol=symbol)
        MonthlySubmission.create(data=token_submission.dict())
        reply = "Submission received"
    except ValueError as error:
        logger.exception(error)
        reply = "Unable to submit provided token. Try again or contact group admin."

    await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)


async def send_monthly_drawing(message: Message):
    """
    Replies with poll for members to vote for token of the month
    Args:
        message: Message to reply to

    """
    logger.info("Executing monthly drawing command")

    try:
        user = message.from_user

        if not await is_admin_user(user=user):
            raise AssertionError("Current user is not an admin of the group")
        submissions = [
            f"{submission.token_name} ({submission.symbol})"
            for submission in MonthlySubmission.all()
        ]
        random.shuffle(submissions)
        options = submissions[:10]
        await message.reply_poll(
            question="Which token will be the token of the month? (Multiple votes allowed)",
            is_anonymous=True,
            allows_multiple_answers=True,
            options=options,
        )
    except (ValueError, AssertionError) as error:
        logger.exception(error)
        reply = "Unable to complete monthly drawing."
        await message.reply(text=reply, parse_mode=ParseMode.MARKDOWN)
