import asyncio
from decimal import Decimal

from config import TELEGRAM_CHAT_ID
from handlers.base import send_message
from handlers.crypto import get_coin_stats
from models import CryptoAlert


async def price_alert_callback(delay: int) -> None:
    """Repetitive task that continues monitoring market for alerted coin mark price until alert is displayed

    Args:
        delay (int): Interval of time to wait in seconds
    """
    alert: CryptoAlert

    while True:
        for alert in CryptoAlert.all():
            crypto = alert.symbol
            sign = alert.sign
            price = alert.price
            token_name = alert.token_name

            send = False
            dip = False

            coin_stats = [
                coin
                for coin in await get_coin_stats(symbol=crypto)
                if coin["token_name"] == token_name
            ][0]

            spot_price = Decimal(coin_stats["price"].replace("$", "").replace(",", ""))

            if sign == "<":
                if price >= spot_price:
                    send = True
                    dip = True
            elif price <= spot_price:
                send = True

            if send:

                price = "${:,}".format(price)
                spot_price = "${:,}".format(spot_price)  # type: ignore

                if dip:
                    response = f":( {crypto} has dipped below {price} and is currently at {spot_price}."
                else:
                    response = f"👋 {crypto} has surpassed {price} and has just reached {spot_price}!"

                alert.remove()
                await send_message(channel_id=TELEGRAM_CHAT_ID, message=response)
            await asyncio.sleep(2)
        await asyncio.sleep(delay)


# if __name__ == '__main__':
#     loop = asyncio.get_event_loop()
#     try:
#         loop.run_until_complete(price_alert_callback(delay=15))
#     finally:
#         loop.run_until_complete(loop.shutdown_asyncgens())
#         loop.close()
