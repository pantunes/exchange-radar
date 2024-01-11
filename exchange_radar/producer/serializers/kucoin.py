from datetime import datetime
from functools import cached_property

from pydantic import Field, computed_field, condecimal, field_validator

from exchange_radar.producer.serializers.base import BaseSerializer


class KucoinTradeSerializer(BaseSerializer):
    symbol: str
    price: condecimal(ge=0, decimal_places=10)
    quantity: condecimal(ge=0, decimal_places=9) = Field(alias="size")
    trade_time: datetime = Field(alias="time")
    side: str = Field(exclude=True)

    @field_validator("symbol")
    def symbol_normalization(cls, v) -> str:
        return v.replace("-", "")

    @field_validator("trade_time", mode="before")
    def trade_time_before(cls, v) -> int:
        return int(v[:13])

    @computed_field
    @cached_property
    def is_seller(self) -> bool:
        return True if self.side == "sell" else False

    @computed_field
    def exchange(self) -> str:
        return "Kucoin"
