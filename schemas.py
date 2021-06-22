import re

from pydantic import BaseModel
from pydantic.class_validators import validator
from pydantic.error_wrappers import ValidationError


class Coin(BaseModel):
    symbol: str = ''
    address: str = ''

    @validator('symbol')
    def symbol_is_alphanumeric(cls, value: str):
        assert value.isalnum(), f'{value} is not a valid symbol'
        return value

    @validator('address')
    def is_valid_address(cls, value: str):
        if re.match(r"^0x\w+", value) is None:
            raise ValidationError(f"'{value}' is not a valid contract address")
        return value
