from datetime import datetime

from pydantic import Field, computed_field, condecimal

from exchange_radar.producer.serializers.base import BaseSerializer


class BinanceTradeSerializer(BaseSerializer):
    symbol: str = Field(alias="s")
    price: condecimal(ge=0, decimal_places=8) = Field(alias="p")
    quantity: condecimal(ge=0, decimal_places=8) = Field(alias="q")
    trade_time: datetime = Field(alias="T")
    is_seller: bool = Field(alias="m")

    @computed_field
    def exchange(self) -> str:
        return "Binance"
