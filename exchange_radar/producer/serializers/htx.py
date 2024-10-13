from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import Annotated

from pydantic import Field, computed_field, field_validator

from exchange_radar.producer.serializers.base import BaseSerializer


class HtxTradeSerializer(BaseSerializer):
    symbol: str = Field(alias="channel")
    price: Annotated[Decimal, Field(ge=0, decimal_places=8)]
    quantity: Annotated[Decimal, Field(ge=0, decimal_places=8, alias="amount")]
    trade_time: datetime = Field(alias="ts")
    direction: str = Field(exclude=True)

    def __init__(self, *args, **kwargs):
        kwargs["price"] = str(kwargs["price"])
        kwargs["amount"] = str(kwargs["amount"])
        super().__init__(*args, **kwargs)

    @field_validator("symbol")  # noqa
    @classmethod
    def symbol_normalization(cls, v) -> str:
        return "".join(v.split(".")[1]).upper()

    @computed_field  # type: ignore
    @cached_property
    def is_seller(self) -> bool:
        return self.direction == "sell"

    @computed_field
    def exchange(self) -> str:
        return "HTX"
