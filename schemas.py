import re
from decimal import Decimal
from numbers import Real
from typing import Union, Optional

from pydantic import BaseModel
from pydantic.class_validators import validator, root_validator
from uniswap.types import AddressLike
from web3 import Web3

from config import BUY, SELL
from models import TelegramGroupMember


def is_valid_address(value: str):
    if re.match(r"^0x\w+", value) is None:
        raise ValueError(f"'{value}' is not a valid contract address")
    return value


def is_positive_number(value: Real):
    if value < Decimal(0):
        raise ValueError("Expected a positive value")
    return value


class Coin(BaseModel):
    symbol: str = ''
    address: Union[str, AddressLike] = ''
    platform: str = ''

    @validator('symbol')
    def symbol_is_alphanumeric(cls, value: str):
        if not value.isalnum():
            raise ValueError(f'{value} is not a valid symbol')
        return value

    @validator('address')
    def check_address(cls, value: Union[str, AddressLike]):
        return Web3.toChecksumAddress(is_valid_address(value))

    @validator('platform')
    def check_platform(cls, value: str):
        value = value.upper()
        if value not in ("BSC",):
            raise ValueError("Invalid platform")
        return value


class TokenAlert(BaseModel):
    id: Optional[int]
    symbol: str = ''
    sign: str = ''
    price: Decimal = 0.0

    _validate_price = validator('price', allow_reuse=True)(is_positive_number)

    @validator('sign')
    def is_valid_sign(cls, value: str):
        if value in {"<", ">"}:
            return value
        raise ValueError("Expected a '<' or '>' sign")

    class Config:
        orm_mode = True

class BinanceChain(BaseModel):
    id: Optional[int]
    address: str = ''
    private_key: str = ''
    telegram_group_member: int

    _validate_address = validator('address',
                                  allow_reuse=True)(is_valid_address)

    @validator('telegram_group_member', pre=True)
    def check_telegram_group_member(cls, value: TelegramGroupMember):
        return value.id

    class Config:
        orm_mode = True


class User(BaseModel):
    id: int
    # bsc_address: Optional[str] = ''
    # bsc_private_key: Optional[str] = ''
    kucoin_api_key: Optional[str] = ''
    kucoin_api_secret: Optional[str] = ''
    kucoin_api_passphrase: Optional[str] = ''

    bsc: BinanceChain

    class Config:
        orm_mode = True


class TradeCoin(Coin):
    amount: Decimal
    side: str

    _validate_amount = validator('amount', allow_reuse=True)(is_positive_number)

    @validator('side')
    def is_valid_side(cls, value: str):
        if value not in (BUY, SELL):
            raise ValueError(f"Expected side to be either '{BUY}' or '{SELL}'")
        return value


class Chart(Coin):
    time_frame: int
    ticker: str

    _validate_time_frame = validator('time_frame',
                                     allow_reuse=True)(is_positive_number)

    @root_validator
    def check_ticker(cls, values):
        """Check order id"""
        ticker = values.get('ticker', '').upper()

        if not ticker:
            raise ValueError(
                "Expected a coin symbol with optional base (defaults to USD). Ex: BTC or BTC-USD"
            )
        if "-" not in ticker:
            ticker = f"{ticker}-USD"
        else:
            symbols = ticker.split('-')
            if symbols[0] == symbols[1]:
                raise ValueError(f"Can't compare *{symbols[0]}* to itself.")

        values['ticker'] = ticker
        return values


class CandleChart(Chart):
    resolution: str

    @validator('resolution')
    def validate_resolution(cls, value: str):
        resolutions = {'m': 'MINUTE', 'h': 'HOUR', 'd': "DAY"}
        value = value.lower()
        if value not in ('m', 'h', 'd'):
            raise ValueError("Expected resolution in 'm', 'h', or 'd'")
        return resolutions[value]
