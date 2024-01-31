from datetime import datetime
from functools import cached_property

from pydantic import Field, computed_field, condecimal, field_validator

from exchange_radar.producer.serializers.base import BaseSerializer


class KrakenTradeSerializer(BaseSerializer):
    symbol: str
    price: condecimal(ge=0, decimal_places=12)
    quantity: condecimal(ge=0, decimal_places=9)
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

    @computed_field
    @cached_property
    def is_seller(self) -> bool:
        return self.side == "s"

    @computed_field
    def exchange(self) -> str:
        return "Kraken"
