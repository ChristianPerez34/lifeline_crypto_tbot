import asyncio
from handler.base import send_message
from handler.bot import (
    KUCOIN_API_KEY,
    KUCOIN_API_PASSPHRASE,
    KUCOIN_API_SECRET,
    TELEGRAM_CHAT_ID,
)
from kucoin.client import Client
from kucoin.asyncio import KucoinSocketManager
from handler import logger
from aiogram.types import ParseMode
from aiogram.utils.markdown import bold


async def kucoin_bot():

    active_orders = {}

    async def deal_msg(msg):
        if msg["topic"] == "/contractMarket/tradeOrders":
            data = msg["data"]
            logger.info(data)
            logger.info(active_orders)

            if data["type"] == "filled":
                symbol = data["symbol"][:-1]
                text = f"Futures Contract ⌛️\n\nCoin: {bold(symbol)}\nClosed Position"

                if symbol in active_orders:
                    order = active_orders[symbol]

                    entry = order["entry"]
                    side = "SHORT" if data["side"] == "sell" else "LONG"

                    if side == order["side"]:
                        text = (
                            f"Futures Contract ⏳\n\n"
                            f"Coin: {bold(symbol)}\n"
                            f"LONG/SHORT: {bold(side)}\n"
                            f"Entry: {bold(entry)}\n"
                            f"Leverage: {bold('10-20x')}\n"
                            f"Take Profit: {bold('At Your Discretion')}\n"
                            f"Stop Loss: {bold('At Your Discretion')}\n"
                        )
                    else:
                        active_orders.pop(symbol, None)
                await send_message(
                    channel_id=TELEGRAM_CHAT_ID,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                )
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
                        "is_active": True,
                    }

    # is private
    client = Client(KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE)

    ksm = await KucoinSocketManager.create(None, client, deal_msg, private=True)
    await ksm.subscribe("/contractMarket/tradeOrders")

    while True:
        await asyncio.sleep(20)
