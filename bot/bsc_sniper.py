import asyncio
from decimal import Decimal
from typing import Union

from web3.exceptions import BadFunctionCallOutput
from web3.types import Address, ChecksumAddress

from api.bsc import PancakeSwap
from app import logger
from config import BUY
from handlers.base import send_message


def token_has_liquidity(token, pancake_swap) -> bool:
    """
    Verifies if token has liquidity
    Args:
        token: BEP20 token
        pancake_swap: PancakeSwap wrapper API

    Returns: Boolean indicating token has liquidity

    """
    logger.info("Verifying %s has liquidity", token)
    has_liquidity = False
    try:
        pair_address = pancake_swap.get_token_pair_address(token=token)
        abi = pancake_swap.get_contract_abi(abi_type="liquidity")
        contract = pancake_swap.web3.eth.contract(address=pair_address, abi=abi)
        liquidity_reserves = contract.functions.getReserves().call()
        has_liquidity = max(liquidity_reserves[:2]) > 0
    except BadFunctionCallOutput:
        logger.exception("Supported LP does not exist for this token.")
    return has_liquidity


async def pancake_swap_sniper(
    chat_id: int,
    token: Union[Address, ChecksumAddress, str],
    amount: Decimal,
    pancake_swap: PancakeSwap,
) -> None:
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
            reply = f"Sniped token 🎯.\n\nView token here: https://poocoin.app/tokens/{token}\n\n"  # type: ignore
            reply += pancake_swap.swap_tokens(
                token=token, amount_to_spend=amount, side=BUY, is_snipe=True
            )
            await send_message(channel_id=chat_id, message=reply)
        await asyncio.sleep(2)
