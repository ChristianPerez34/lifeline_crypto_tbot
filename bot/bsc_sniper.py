import asyncio
import json
from decimal import Decimal

from uniswap.types import AddressLike
from web3 import Web3
from web3.datastructures import AttributeDict

from api.bsc import CONTRACT_ADDRESSES, PancakeSwap
from config import BUY
from handlers import logger
from handlers.base import send_message


def handle_event(chat_id: int, token: AddressLike, pancake_swap: PancakeSwap, event: AttributeDict) -> bool:
    wbnb = CONTRACT_ADDRESSES['WBNB']
    data = json.loads(Web3.toJSON(event))
    args = data['args']
    token_a, token_b = Web3.toChecksumAddress(args["token0"]), Web3.toChecksumAddress(args["token1"])

    if (token_a == wbnb and token_b == token) or (token_b == wbnb and token_a == token):
        logger.info("Detected token liquidity pair was created for %s", token)
        pancake_swap.swap_tokens(token=token, amount_to_spend=0.07, side=BUY)
        send_message(channel_id=chat_id,
                     message=f"Sniped token 🎯.\n\nView token here: https://poocoin.app/tokens/{token}")
        return True
    return False


def token_has_liquidity(token, pancake_swap) -> bool:
    """
    Verifies if token has liquidity
    Args:
        token: BEP20 token
        pancake_swap: PancakeSwap wrapper API

    Returns: Boolean indicating token has liquidity

    """
    pair_address = pancake_swap.get_token_pair_address(token=token)
    abi = pancake_swap.get_contract_abi(abi_type='liquidity')
    contract = pancake_swap.web3.eth.contract(address=pair_address, abi=abi)
    liquidity_reserves = contract.functions.getReserves().call()
    return max(liquidity_reserves[:2]) > 0


async def pancake_swap_sniper(chat_id: int, token: AddressLike, amount: Decimal, pancake_swap: PancakeSwap) -> None:
    """
    Snipes token on PancakeSwap
    Args:
        chat_id (int): Telegram chat id
        token: BEP20 token to snipe
        amount: Amount of BNB to spend to buy token
        pancake_swap: PancakeSwap wrapper API
    """
    has_liquidity = False
    while not has_liquidity:
        has_liquidity = token_has_liquidity(token, pancake_swap)

        if has_liquidity:
            reply = f"Sniped token 🎯.\n\nView token here: https://poocoin.app/tokens/{token}\n\n"
            reply += pancake_swap.swap_tokens(token=token, amount_to_spend=amount, side=BUY)
            await send_message(channel_id=chat_id,
                               message=reply)
        await asyncio.sleep(2)
