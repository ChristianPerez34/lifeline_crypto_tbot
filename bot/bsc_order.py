import asyncio

from api.bsc import PancakeSwap
from config import BUY, SELL, STOP
from schemas import LimitOrder


async def limit_order_executor(order: LimitOrder):
    order_executed = False
    user = order.telegram_group_member
    bsc = user.bsc
    dex = PancakeSwap(address=bsc.address, key=bsc.private_key)
    token = dex.get_token(address=order.address)
    token_price = dex.get_decimal_representation(
        quantity=dex.get_token_price(token=order.address, as_busd_per_token=True),
        decimals=token.decimals,
    )
    target_price = order.target_price
    trade_direction = order.trade_direction

    while not order_executed:

        if trade_direction == BUY and token_price <= target_price:
            dex.swap_tokens(
                token=order.address, amount_to_spend=order.bnb_amount, side=BUY
            )
            order_executed = True
        elif (trade_direction == SELL and token_price >= target_price) or (
            trade_direction == STOP and token_price <= target_price
        ):
            dex.swap_tokens(
                token=order.address, amount_to_spend=order.bnb_amount, side=SELL
            )
            order_executed = True
        await asyncio.sleep(2)
