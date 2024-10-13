from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import Annotated

from pydantic import Field, computed_field, field_validator

from exchange_radar.producer.serializers.base import BaseSerializer


class KucoinTradeSerializer(BaseSerializer):
    symbol: str
    price: Annotated[Decimal, Field(ge=0, decimal_places=10)]
    quantity: Annotated[Decimal, Field(ge=0, decimal_places=9, alias="size")]
    trade_time: datetime = Field(alias="time")
    side: str = Field(exclude=True)

    @field_validator("symbol")  # noqa
    @classmethod
    def symbol_normalization(cls, v) -> str:
        return v.replace("-", "")

    @field_validator("trade_time", mode="before")  # noqa
    @classmethod
    def trade_time_before(cls, v) -> int:
        return int(v[:13])

    @computed_field  # type: ignore
    @cached_property
    def is_seller(self) -> bool:
        return self.side == "sell"

    @computed_field
    def exchange(self) -> str:
        return "KuCoin"
