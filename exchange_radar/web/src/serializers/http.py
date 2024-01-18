from dataclasses import dataclass

from exchange_radar.web.src.serializers.mixins import Validations
from exchange_radar.web.src.settings import base as settings


@dataclass
class ParamsInputSerializer(Validations):
    coin: str

    def validate_coin(self, value, **_) -> str:  # noqa
        if value not in settings.COINS:
            raise ValueError(f"Invalid coin: {value}")
        return value


@dataclass
class IndexParamsInputSerializer(ParamsInputSerializer):
    coin: str = "BTC"
