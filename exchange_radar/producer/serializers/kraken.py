from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import Annotated

from pydantic import Field, computed_field, field_validator

from exchange_radar.producer.serializers.base import BaseSerializer


class KrakenTradeSerializer(BaseSerializer):
    symbol: str
    price: Annotated[Decimal, Field(ge=0, decimal_places=12)]
    quantity: Annotated[Decimal, Field(ge=0, decimal_places=9)]
    trade_time: datetime
    side: str = Field(exclude=True)

    @field_validator("symbol")  # noqa
    @classmethod
    def symbol_normalization(cls, v) -> str:
        if v[:4] == "XBT/":
            v = v.replace("XBT/", "BTC/")
        elif v[-4:] == "/XBT":
            v = v.replace("/XBT", "/BTC")
        return v.replace("/", "")

    @field_validator("trade_time", mode="before")  # noqa
    @classmethod
    def trade_time_before(cls, v) -> int:
        return int(v[:10])

    @computed_field  # type: ignore
    @cached_property
    def is_seller(self) -> bool:
        return self.side == "s"

    @computed_field
    def exchange(self) -> str:
        return "Kraken"
