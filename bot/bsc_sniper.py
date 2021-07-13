# import the following dependencies
import asyncio
import json

from uniswap.types import AddressLike
from web3 import Web3
# define function to handle events and print to the console
from web3.datastructures import AttributeDict

from api.bsc import CONTRACT_ADDRESSES, PancakeSwap
# add your blockchain connection information
from handlers import logger
from handlers.base import send_message


def handle_event(chat_id: int, token: AddressLike, pancake_swap: PancakeSwap, event: AttributeDict) -> bool:
    wbnb = CONTRACT_ADDRESSES['WBNB']
    data = json.loads(Web3.toJSON(event))
    args = data['args']
    pair_address = args['pair']
    token_a, token_b = Web3.toChecksumAddress(args["token0"]), Web3.toChecksumAddress(args["token1"])

    if (token_a == wbnb and token_b == token) or (token_b == wbnb and token_a == token):
        logger.info("Detected token liquidity pair was created for %s", token)
        send_message(channel_id=chat_id,
                     message=f"Sniped token 🎯.\n\nView token here: https://poocoin.app/tokens/{token}")

        # abi = pancake_swap.get_contract_abi(abi_type='liquidity')
        # contract = pancake_swap.web3.eth.contract(address=pair_address, abi=abi)
        # liquidity_reserves = contract.functions.getReserves().call()
        # wbnb_liquidity_balance = liquidity_reserves[reserve]
        # wbnb_price = pancake_swap.get_token_price(token=wbnb)
        # amount_of_bnb_in_liquidity = wbnb_liquidity_balance / wbnb_price
        # usd_amount_of_bnb_in_liquidity = amount_of_bnb_in_liquidity.quantize(Decimal('0.01'))

        # Making sure there is at least $10k in liquidity to minimize risk of rug pull
        # if usd_amount_of_bnb_in_liquidity > 40000:
        return True
    return False
    # and whatever


# when main is called
# create a filter for the latest block and look for the "PairCreated" event for the uniswap factory contract
# run an async loop
# try to run the log_loop function above every 2 seconds
def token_has_liquidity(token, pancake_swap):
    pair_address = pancake_swap.get_token_pair_address(token=token)
    abi = pancake_swap.get_contract_abi(abi_type='liquidity')
    contract = pancake_swap.web3.eth.contract(address=pair_address, abi=abi)
    liquidity_reserves = contract.functions.getReserves().call()
    return max(liquidity_reserves[:2]) > 0


async def pancake_swap_sniper(chat_id: int, token: AddressLike, pancake_swap: PancakeSwap, event_filter):
    # pair_found = False
    # while not pair_found:
    #     for pair_created in event_filter.get_new_entries():
    #         logger.info("PancakeSwap sniping bot pair found")
    #         pair_found = handle_event(chat_id, token, pancake_swap, pair_created)
    #     await asyncio.sleep(2)
    has_liquidity = False
    while not has_liquidity:
        has_liquidity = token_has_liquidity(token, pancake_swap)

        if has_liquidity:
            await send_message(channel_id=chat_id,
                               message=f"Sniped token 🎯.\n\nView token here: https://poocoin.app/tokens/{token}")
        # for pair_created in event_filter.get_new_entries():
        #     logger.info("PancakeSwap sniping bot pair found")
        #     pair_found = handle_event(chat_id, token, pancake_swap, pair_created)
        await asyncio.sleep(2)
