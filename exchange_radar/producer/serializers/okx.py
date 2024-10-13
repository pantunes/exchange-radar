from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import Annotated

from pydantic import Field, computed_field, field_validator

from exchange_radar.producer.serializers.base import BaseSerializer


class OkxTradeSerializer(BaseSerializer):
    symbol: str = Field(alias="instId")
    price: Annotated[Decimal, Field(ge=0, decimal_places=8, alias="px")]
    quantity: Annotated[Decimal, Field(ge=0, decimal_places=8, alias="sz")]
    trade_time: datetime = Field(alias="ts")
    side: str = Field(exclude=True)

    @field_validator("symbol")  # noqa
    @classmethod
    def symbol_normalization(cls, v) -> str:
        return v.replace("-", "")

    @computed_field  # type: ignore
    @cached_property
    def is_seller(self) -> bool:
        return self.side == "sell"

    @computed_field
    def exchange(self) -> str:
        return "OKX"
