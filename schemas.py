import re
from decimal import Decimal

from pydantic import BaseModel
from pydantic.class_validators import validator

from config import BUY, SELL


def is_valid_address(value: str):
    if re.match(r"^0x\w+", value) is None:
        raise ValueError(f"'{value}' is not a valid contract address")
    return value


def is_positive_number(value: Decimal):
    if value < Decimal(0):
        raise ValueError("Expected a positive value")


class Coin(BaseModel):
    symbol: str = ''
    address: str = ''

    _validate_address = validator('address', allow_reuse=True)(is_valid_address)

    @validator('symbol')
    def symbol_is_alphanumeric(cls, value: str):
        assert value.isalnum(), f'{value} is not a valid symbol'
        return value


class Alert(Coin):
    sign: str = ''
    price: Decimal = 0.0

    _validate_price = validator('price', allow_reuse=True)(is_positive_number)

    @validator('sign')
    def is_valid_sign(cls, value: str):
        if value not in ("<", ">"):
            raise ValueError("Expected a '<' or '>' sign")
        return value


class User(BaseModel):
    id: int
    bsc_address: str
    bsc_private_key: str
    kucoin_api_key: str
    kucoin_api_secret: str
    kucoin_api_passphrase: str

    _validate_address = validator('bsc_address', allow_reuse=True)(is_valid_address)

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
