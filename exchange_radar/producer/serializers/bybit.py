from datetime import datetime
from functools import cached_property

from pydantic import Field, computed_field, condecimal

from exchange_radar.producer.serializers.base import BaseSerializer


class BybitTradeSerializer(BaseSerializer):
    symbol: str = Field(alias="s")
    price: condecimal(ge=0, decimal_places=8) = Field(alias="p")
    quantity: condecimal(ge=0, decimal_places=8) = Field(alias="v")
    trade_time: datetime = Field(alias="T")
    side: str = Field(alias="S", exclude=True)

    @computed_field
    @cached_property
    def is_seller(self) -> bool:
        return self.side == "Sell"

    @computed_field
    def exchange(self) -> str:
        return "Bybit"
