from datetime import datetime
from functools import cached_property

from pydantic import Field, computed_field, condecimal, field_validator

from exchange_radar.producer.serializers.base import BaseSerializer


class OkxTradeSerializer(BaseSerializer):
    symbol: str = Field(alias="instId")
    price: condecimal(ge=0, decimal_places=8) = Field(alias="px")
    quantity: condecimal(ge=0, decimal_places=8) = Field(alias="sz")
    trade_time: datetime = Field(alias="ts")
    side: str = Field(exclude=True)

    @field_validator("symbol")  # noqa
    @classmethod
    def symbol_normalization(cls, v) -> str:
        return v.replace("-", "")

    @computed_field
    @cached_property
    def is_seller(self) -> bool:
        return self.side == "sell"

    @computed_field
    def exchange(self) -> str:
        return "OKX"
