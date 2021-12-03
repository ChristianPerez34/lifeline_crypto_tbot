import datetime
import re
from decimal import Decimal
from numbers import Real
from typing import Optional, Union

from inflection import humanize
from pydantic import BaseModel
from pydantic.class_validators import root_validator, validator
from pydantic.fields import Field
from web3 import Web3
from web3.types import Address, ChecksumAddress

from config import BUY, SELL, STOP
from models import TelegramGroupMember


def is_positive_number(value: Real):
    if value < Decimal(0):
        raise ValueError("Expected a positive value")
    return value


def check_telegram_group_member(value: Union[int, TelegramGroupMember]):
    if isinstance(value, int):
        return value
    return value.id


def validate_trade_direction(value: str):
    value = value.upper()
    if value not in (BUY, SELL, STOP):
        raise ValueError("Valid options are either 'buy'|'sell'|'stop'")
    return value


class Token(BaseModel):
    address: Union[Address, ChecksumAddress, str] = ""

    @validator("address")
    def check_address(cls, value: Union[Address, ChecksumAddress, str]):
        if isinstance(value, bytes):
            value = value.decode()
        if re.match(r"^0x\w+", value) is None:  # type: ignore
            raise ValueError(f"'{value}' is not a valid contract address")  # type: ignore
        return Web3.toChecksumAddress(value)


class Platform(BaseModel):
    network: Optional[str]

    @validator("network")
    def check_platform(cls, value: str):
        value = value.upper()
        if value and value not in ("BSC", "ETH", "MATIC", "COINBASE"):
            raise ValueError("Invalid network. Expected one of eth|bsc|matic")
        return value


class Coin(Token, Platform):
    symbol: str = ""

    @validator("symbol")
    def symbol_is_alphanumeric(cls, value: str):
        if not value.isalnum():
            raise ValueError(f"{value} is not a valid symbol")
        return value


class TokenAlert(BaseModel):
    id: Optional[int]
    coin_id: Optional[str]
    symbol: str = ""
    sign: str = ""
    price: Decimal = Decimal(0)

    _validate_price = validator("price", allow_reuse=True)(is_positive_number)

    @validator("sign")
    def is_valid_sign(cls, value: str):
        if value in {"<", ">"}:
            return value
        raise ValueError("Expected a '<' or '>' sign")

    class Config:
        orm_mode = True


class Network(Token):
    id: Optional[int]
    private_key: str = ""
    telegram_group_member: int

    _check_telegram_group_member = validator(
        "telegram_group_member", allow_reuse=True, pre=True
    )(check_telegram_group_member)


class BinanceChain(Network):
    class Config:
        orm_mode = True


class EthereumChain(Network):
    class Config:
        orm_mode = True


class MaticChain(Network):
    class Config:
        orm_mode = True


class CoinBaseExchange(BaseModel):
    id: Optional[int]
    api_key: str
    api_secret: str
    api_passphrase: str
    telegram_group_member: int

    class Config:
        orm_mode = True

    _check_telegram_group_member = validator(
        "telegram_group_member", allow_reuse=True, pre=True
    )(check_telegram_group_member)


class User(BaseModel):
    id: int
    kucoin_api_key: Optional[str] = ""
    kucoin_api_secret: Optional[str] = ""
    kucoin_api_passphrase: Optional[str] = ""

    bsc: Optional[BinanceChain]
    eth: Optional[EthereumChain]
    matic: Optional[MaticChain]
    coinbase: Optional[CoinBaseExchange]

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

    _validate_trade_direction = validator("trade_direction", allow_reuse=True)(
        validate_trade_direction
    )

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class CoinbaseOrder(BaseModel):
    order_type: str
    trade_direction: str
    symbol: str
    amount: float
    limit_price: float

    _validate_trade_direction = validator("trade_direction", allow_reuse=True)(
        validate_trade_direction
    )
    _validate_amount = validator("amount", allow_reuse=True)(is_positive_number)
    _validate_limit_price = validator("limit_price", allow_reuse=True)(
        is_positive_number
    )

    @validator("symbol")
    def uppercase_symbol(cls, value: str):
        return value.upper()

    @validator("order_type")
    def validate_order_type(cls, value: str):
        value = value.lower()

        if value not in ("market", "limit"):
            raise ValueError("Expected either 'market' or 'limit'")
        return value


class TokenSubmission(BaseModel):
    id: Optional[int]
    symbol: str
    token_name: str
    submission_date: datetime.date = Field(default=datetime.date.today())

    @validator("token_name")
    def check_token_name(cls, value: str):
        if not value:
            raise ValueError("Token name must be filled")
        return humanize(value)

    @validator("symbol")
    def check_symbol(cls, value: str):
        return value.upper()

    class Config:
        orm_mode = True
