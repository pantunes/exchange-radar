from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field, computed_field

from exchange_radar.producer.serializers.base import BaseSerializer


class BinanceTradeSerializer(BaseSerializer):
    symbol: str = Field(alias="s")
    price: Annotated[Decimal, Field(ge=0, decimal_places=8, alias="p")]
    quantity: Annotated[Decimal, Field(ge=0, decimal_places=8, alias="q")]
    trade_time: datetime = Field(alias="T")
    is_seller: bool = Field(alias="m")

    @computed_field
    def exchange(self) -> str:
        return "Binance"
