from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import Annotated

from pydantic import Field, computed_field

from exchange_radar.producer.serializers.base import FeedSerializer


class BybitTradeSerializer(FeedSerializer):
    symbol: str = Field(alias="s")
    price: Annotated[Decimal, Field(ge=0, decimal_places=8, alias="p")]
    quantity: Annotated[Decimal, Field(ge=0, decimal_places=8, alias="v")]
    trade_time: datetime = Field(alias="T")
    side: str = Field(alias="S", exclude=True)

    @computed_field  # type: ignore
    @cached_property
    def is_seller(self) -> bool:
        return self.side == "Sell"

    @computed_field
    def exchange(self) -> str:
        return "Bybit"
