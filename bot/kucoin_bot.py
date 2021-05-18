import asyncio

from aiogram.utils.markdown import bold, text
from kucoin_futures.client import WsToken
from kucoin_futures.ws_client import KucoinFuturesWsClient

from bot import (KUCOIN_API_KEY, KUCOIN_API_PASSPHRASE, KUCOIN_API_SECRET,
                 TELEGRAM_CHAT_ID, active_orders)
from handler import logger
from handler.base import send_message


async def kucoin_bot():
    async def deal_msg(msg):
        if msg["topic"] == "/contractMarket/tradeOrders":
            data = msg["data"]
            logger.info(data)

            if data["type"] == "filled":
                symbol = data["symbol"][:-1]
                symbol = symbol.replace("XBTUSDT", "BTCUSDT")
                message = (
                    f"Futures Contract ⌛️\n\nCoin: {bold(symbol)}\nClosed Position"
                )

                if symbol in active_orders:
                    order = active_orders[symbol]

                    entry = order["entry"]
                    side = "SHORT" if data["side"] == "sell" else "LONG"

                    if side == order["side"]:
                        message = text(
                            (
                                f"Futures Contract ⏳\n\n"
                                f"Coin: {bold(symbol)}\n"
                                f"LONG/SHORT: {bold(side)}\n"
                                f"Entry: {entry}\n"
                                f"Leverage: {bold('10')}-{bold('20x')}\n"
                                f"Take Profit: {bold('At Your Discretion')}\n"
                                f"Stop Loss: {bold('At Your Discretion')}\n"
                            )
                        )
                    else:
                        active_orders.pop(symbol, None)
                await send_message(channel_id=TELEGRAM_CHAT_ID, text=message)
            elif data["type"] == "match":
                symbol = data["symbol"][:-1]

                # Webhook displays BTCUSDT symbol as XBTUSDT, so must be replaced with appropriate symbol
                symbol = symbol.replace("XBTUSDT", "BTCUSDT")
                entry = data["matchPrice"]
                if symbol in active_orders:
                    active_orders[symbol][
                        "entry"
                    ] = f"{active_orders[symbol]['entry']}-{entry}"
                else:
                    active_orders[symbol] = {
                        "entry": entry,
                        "side": "SHORT" if data["side"] == "sell" else "LONG",
                    }
        elif msg["topic"] == "/contractMarket/advancedOrders":
            data = msg["data"]
            if data["type"] != "cancel":
                symbol = data["symbol"][:-1]
                order = active_orders[symbol]
                stop_price = data["stopPrice"]
                if data["stop"] == "up" and order["take_profit"] != stop_price:
                    order["take_profit"] = stop_price
                else:
                    order["stop_loss"] = stop_price
                message = text(
                    (
                        f"Futures Contract ⏳\n\nPosition Update ❗️❗️❗️\n\n"
                        f"Coin: {bold(symbol)}\n"
                        f"LONG/SHORT: {order['side']}\n"
                        f"Entry: {order['entry']}\n"
                        f"Leverage: 10-20x\n"
                        f"Take Profit: {order['take_profit']}\n"
                        f"Stop Loss: {order['stop_loss']}\n"
                    )
                )
                await send_message(channel_id=TELEGRAM_CHAT_ID, text=message)

    # is private
    client = WsToken(
        key=KUCOIN_API_KEY,
        secret=KUCOIN_API_SECRET,
        passphrase=KUCOIN_API_PASSPHRASE,
        is_sandbox=False,
        url="",
    )
    loop = asyncio.get_event_loop()
    ws_client = await KucoinFuturesWsClient.create(loop, client, deal_msg, private=True)

    await ws_client.subscribe("/contractMarket/tradeOrders")
    await ws_client.subscribe("/contractMarket/advancedOrders")

    while True:
        await asyncio.sleep(20)
