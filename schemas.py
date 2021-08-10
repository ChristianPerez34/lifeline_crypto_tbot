import re
from decimal import Decimal
from numbers import Real
from typing import Optional, Union

from pydantic import BaseModel
from pydantic.class_validators import root_validator, validator
from uniswap.types import AddressLike
from web3 import Web3

from config import BUY, SELL, STOP
from models import TelegramGroupMember


def is_positive_number(value: Real):
    if value < Decimal(0):
        raise ValueError("Expected a positive value")
    return value


class Token(BaseModel):
    address: Union[str, AddressLike] = ""

    @validator("address")
    def check_address(cls, value: Union[str, AddressLike]):
        if re.match(r"^0x\w+", value) is None:
            raise ValueError(f"'{value}' is not a valid contract address")
        return Web3.toChecksumAddress(value)


class Coin(Token):
    symbol: str = ""
    platform: Optional[str]

    @validator("symbol")
    def symbol_is_alphanumeric(cls, value: str):
        if not value.isalnum():
            raise ValueError(f"{value} is not a valid symbol")
        return value

    @validator("platform")
    def check_platform(cls, value: str):
        value = value.upper()
        if value and value not in ("BSC",):
            raise ValueError("Invalid platform")
        return value


class TokenAlert(BaseModel):
    id: Optional[int]
    symbol: str = ""
    sign: str = ""
    price: Decimal = 0.0

    _validate_price = validator("price", allow_reuse=True)(is_positive_number)

    @validator("sign")
    def is_valid_sign(cls, value: str):
        if value in {"<", ">"}:
            return value
        raise ValueError("Expected a '<' or '>' sign")

    class Config:
        orm_mode = True


class BinanceChain(Token):
    id: Optional[int]
    private_key: str = ""
    telegram_group_member: int

    @validator("telegram_group_member", pre=True)
    def check_telegram_group_member(cls, value: Union[int, TelegramGroupMember]):
        if isinstance(value, int):
            return value
        return value.id

    class Config:
        orm_mode = True


class User(BaseModel):
    id: int
    # bsc_address: Optional[str] = ''
    # bsc_private_key: Optional[str] = ''
    kucoin_api_key: Optional[str] = ""
    kucoin_api_secret: Optional[str] = ""
    kucoin_api_passphrase: Optional[str] = ""

    bsc: BinanceChain

    class Config:
        orm_mode = True


class TradeCoin(Coin):
    amount: Decimal
    side: str

    _validate_amount = validator("amount", allow_reuse=True)(is_positive_number)

    @validator("side")
    def is_valid_side(cls, value: str):
        if value not in (BUY, SELL):
            raise ValueError(f"Expected side to be either '{BUY}' or '{SELL}'")
        return value


class Chart(Coin):
    time_frame: int
    ticker: str

    _validate_time_frame = validator("time_frame", allow_reuse=True)(is_positive_number)

    @root_validator
    def check_ticker(cls, values):
        """Check order id"""
        ticker = values.get("ticker", "").upper()

        if not ticker:
            raise ValueError(
                "Expected a coin symbol with optional base (defaults to USD). Ex: BTC or BTC-USD"
            )
        if "-" not in ticker:
            ticker = f"{ticker}-USD"
        else:
            symbols = ticker.split("-")
            if symbols[0] == symbols[1]:
                raise ValueError(f"Can't compare *{symbols[0]}* to itself.")

        values["ticker"] = ticker
        return values


class CandleChart(Chart):
    resolution: str

    @validator("resolution")
    def validate_resolution(cls, value: str):
        resolutions = {"m": "MINUTE", "h": "HOUR", "d": "DAY"}
        value = value.lower()
        if value not in ("m", "h", "d"):
            raise ValueError("Expected resolution in 'm', 'h', or 'd'")
        return resolutions[value]


class LimitOrder(Token):
    id: Optional[int]
    trade_direction: str
    target_price: Decimal
    bnb_amount: Decimal
    telegram_group_member: Optional[User]

    @validator("trade_direction")
    def validate_trade_direction(cls, value: str):
        value = value.upper()
        if value not in (BUY, SELL, STOP):
            raise ValueError("Valid options are either 'buy'|'sell'|'stop'")
        return value

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True
