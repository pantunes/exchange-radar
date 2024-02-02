import time
from datetime import datetime, timedelta

from redis_om import get_redis_connection

from exchange_radar.producer.settings.base import REDIS_EXPIRATION
from exchange_radar.producer.utils import get_exchanges

redis = get_redis_connection()


class RedisMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name = datetime.today().date().strftime("%Y-%m-%d")

        with redis.pipeline() as pipe:
            pipe.expire(name=self._name, time=timedelta(days=REDIS_EXPIRATION), nx=True)
            pipe.hsetnx(self._name, f"{self.trade_symbol}_PRICE", float(self.price))  # noqa
            pipe.hsetnx(self._name, f"{self.trade_symbol}_CURRENCY", self.currency)  # noqa
            pipe.hsetnx(self._name, f"{self.trade_symbol}_EXCHANGES", get_exchanges(coin=self.trade_symbol))  # noqa
            pipe.set(f"LAST_TS_{self.exchange.upper()}", time.time())  # noqa
            pipe.execute()

    def volume(self) -> float:
        return redis.hincrbyfloat(self._name, f"{self.trade_symbol}_VOLUME", float(self.quantity))  # noqa

    def volume_trades(self) -> tuple[float, float] | None:
        with redis.pipeline() as pipe:
            if self.is_seller is False:  # noqa
                pipe.hincrbyfloat(
                    self._name,
                    f"{self.trade_symbol}_VOLUME_BUY_ORDERS",  # noqa
                    float(self.quantity),  # noqa
                )
                pipe.hget(self._name, f"{self.trade_symbol}_VOLUME_SELL_ORDERS")  # noqa
            else:
                pipe.hget(self._name, f"{self.trade_symbol}_VOLUME_BUY_ORDERS")  # noqa

                pipe.hincrbyfloat(
                    self._name,
                    f"{self.trade_symbol}_VOLUME_SELL_ORDERS",  # noqa
                    float(self.quantity),  # noqa
                )
            result = pipe.execute()

        try:
            result = float(result[0]), float(result[1])
        except TypeError:
            return None
        return result

    def number_trades(self) -> tuple[int, int] | None:
        with redis.pipeline() as pipe:
            if self.is_seller is False:  # noqa
                pipe.hincrby(self._name, f"{self.trade_symbol}_NUMBER_BUY_ORDERS", 1)  # noqa
                pipe.hget(self._name, f"{self.trade_symbol}_NUMBER_SELL_ORDERS")  # noqa
            else:
                pipe.hget(self._name, f"{self.trade_symbol}_NUMBER_BUY_ORDERS")  # noqa
                pipe.hincrby(self._name, f"{self.trade_symbol}_NUMBER_SELL_ORDERS", 1)  # noqa
            result = pipe.execute()

        try:
            result = int(result[0]), int(result[1])
        except TypeError:
            return None
        return result
