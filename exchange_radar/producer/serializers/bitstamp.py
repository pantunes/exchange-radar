from datetime import datetime
from functools import cached_property

from pydantic import Field, computed_field, condecimal, field_validator

from exchange_radar.producer.serializers.base import BaseSerializer


class BitstampTradeSerializer(BaseSerializer):
    symbol: str = Field(alias="channel")
    price: condecimal(ge=0, decimal_places=8) = Field(alias="price_str")
    quantity: condecimal(ge=0, decimal_places=8) = Field(alias="amount_str")
    trade_time: datetime = Field(alias="timestamp")
    type: int = Field(exclude=True)

    @field_validator("symbol")  # noqa
    @classmethod
    def symbol_normalization(cls, v) -> str:
        return "".join(v.split("_")[-1:]).upper()

    @computed_field
    @cached_property
    def is_seller(self) -> bool:
        return self.type == 1

    @computed_field
    def exchange(self) -> str:
        return "Bitstamp"
