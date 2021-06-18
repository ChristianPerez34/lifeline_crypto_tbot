import asyncio
from decimal import Decimal

from aiogram.utils.markdown import bold
from aiogram.utils.markdown import text
from kucoin_futures.client import WsToken
from kucoin_futures.ws_client import KucoinFuturesWsClient
from requests.exceptions import RequestException

from bot import active_orders
from config import KUCOIN_API_KEY
from config import KUCOIN_API_PASSPHRASE
from config import KUCOIN_API_SECRET
from config import TELEGRAM_CHAT_ID
from handlers import logger
from handlers.base import send_message


async def kucoin_bot():
    async def deal_msg(msg):
        try:
            if msg["topic"] == "/contractMarket/tradeOrders":
                data = msg["data"]
                logger.info(data)
                inline = False

                if data["type"] == "filled":
                    symbol = data["symbol"][:-1]
                    symbol = symbol.replace("XBTUSDT", "BTCUSDT")
                    pnl = active_orders[symbol].get("pnl", "")
                    message = f"Futures Contract ⌛️\n\nCoin: {bold(symbol)}\nClosed Position\nPNL: {pnl}"

                    if symbol in active_orders:
                        order = active_orders[symbol]

                        entries = list(map(Decimal, order["entry"].split("-")))
                        entry = (f"{min(entries)}-{max(entries)}"
                                 if len(entries) > 1 else entries[0])
                        side = "SHORT" if data["side"] == "sell" else "LONG"

                        if side == order["side"]:
                            message = text(
                                (f"Futures Contract ⏳\n\n"
                                 f"Coin: {bold(symbol)}\n"
                                 f"LONG/SHORT: {bold(side)}\n"
                                 f"Entry: {entry}\n"
                                 f"Leverage: {bold('10')}-{bold('20x')}\n"
                                 f"Take Profit: {bold('At Your Discretion')}\n"
                                 f"Stop Loss: {bold('At Your Discretion')}\n"))
                            inline = True
                            data = f"{symbol};{side};"
                        else:
                            data = ""
                            active_orders.pop(symbol, None)
                    await send_message(
                        channel_id=TELEGRAM_CHAT_ID,
                        message=message,
                        inline=inline,
                        data=data,
                    )
                elif data["type"] == "match":
                    symbol = data["symbol"][:-1]

                    # Webhook displays BTCUSDT symbol as XBTUSDT, so must be replaced with appropriate symbol
                    symbol = symbol.replace("XBTUSDT", "BTCUSDT")
                    entry = data["matchPrice"]
                    if symbol in active_orders:
                        active_orders[symbol][
                            "entry"] = f"{active_orders[symbol]['entry']}-{entry}"
                    else:
                        active_orders[symbol] = {
                            "entry": entry,
                            "side":
                            "SHORT" if data["side"] == "sell" else "LONG",
                            "take_profit": "",
                            "stop_loss": "",
                            "pnl": "",
                        }
            elif msg["topic"] == "/contractMarket/advancedOrders":
                data = msg["data"]
                if data["type"] != "cancel":
                    symbol = data["symbol"][:-1]
                    symbol = symbol.replace("XBTUSDT", "BTCUSDT")
                    order = active_orders[symbol]
                    stop_price = data["stopPrice"]
                    if data["stop"] == "up" and order[
                            "take_profit"] != stop_price:
                        order["take_profit"] = stop_price
                    else:
                        order["stop_loss"] = stop_price
                    message = text(
                        (f"Futures Contract ⏳\n\nPosition Update ❗️❗️❗️\n\n"
                         f"Coin: {bold(symbol)}\n"
                         f"LONG/SHORT: {order['side']}\n"
                         f"Entry: {order['entry']}\n"
                         f"Leverage: 10-20x\n"
                         f"Take Profit: {order['take_profit']}\n"
                         f"Stop Loss: {order['stop_loss']}\n"))
                    await send_message(channel_id=TELEGRAM_CHAT_ID,
                                       message=message)
            elif "/contract/position" in msg["topic"]:
                data = msg["data"]
                symbol = msg["topic"].split(":")[1][:-1]
                symbol = symbol.replace("XBTUSDT", "BTCUSDT")
                if symbol in active_orders:
                    active_orders[symbol]["pnl"] = data["unrealisedPnl"]
        except (RequestException, KeyError) as e:
            logger.exception(e)

    # is private
    client = WsToken(
        key=KUCOIN_API_KEY,
        secret=KUCOIN_API_SECRET,
        passphrase=KUCOIN_API_PASSPHRASE,
        is_sandbox=False,
        url="",
    )
    loop = asyncio.get_event_loop()
    ws_client = await KucoinFuturesWsClient.create(loop,
                                                   client,
                                                   deal_msg,
                                                   private=True)

    await ws_client.subscribe("/contractMarket/tradeOrders")
    await ws_client.subscribe("/contractMarket/advancedOrders")

    while True:
        await asyncio.sleep(20)
