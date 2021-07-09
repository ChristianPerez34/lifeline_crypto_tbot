# import the following dependencies
import asyncio
import json

from web3 import Web3
# define function to handle events and print to the console
from web3.datastructures import AttributeDict

from api.bsc import CONTRACT_ADDRESSES


# add your blockchain connection information


def handle_event(chat_id: int, event: AttributeDict):
    data = json.loads(Web3.toJSON(event))
    token_a, token_b = Web3.toChecksumAddress(data['args']["token0"]), Web3.toChecksumAddress(data['args']["token1"])
    token = token_b if token_a == CONTRACT_ADDRESSES['WBNB'] else token_a
    print(Web3.toJSON(event))
    # and whatever


# when main is called
# create a filter for the latest block and look for the "PairCreated" event for the uniswap factory contract
# run an async loop
# try to run the log_loop function above every 2 seconds
async def pancake_swap_sniper(chat_id: int, event_filter):
    pair_found = False
    while not pair_found:
        for pair_created in event_filter.get_new_entries():
            handle_event(chat_id, pair_created)
            pair_found = True
        await asyncio.sleep(2)
