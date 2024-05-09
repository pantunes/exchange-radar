import time
from datetime import timedelta

from redis_om import get_redis_connection

from exchange_radar.producer.settings.base import REDIS_EXPIRATION
from exchange_radar.producer.utils import get_exchanges

redis = get_redis_connection()


class RedisMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # noinspection PyUnresolvedReferences
        self._name = self.trade_time.date().strftime("%Y-%m-%d")

        with redis.pipeline() as pipe:
            pipe.expire(name=self._name, time=timedelta(days=REDIS_EXPIRATION), nx=True)
            # noinspection PyUnresolvedReferences
            pipe.hsetnx(self._name, f"{self.trade_symbol}_PRICE", float(self.price))
            # noinspection PyUnresolvedReferences
            pipe.hsetnx(self._name, f"{self.trade_symbol}_CURRENCY", self.currency)
            # noinspection PyUnresolvedReferences
            pipe.hsetnx(self._name, f"{self.trade_symbol}_EXCHANGES", get_exchanges(coin=self.trade_symbol))
            # noinspection PyUnresolvedReferences
            pipe.set(f"LAST_TS_{self.exchange.upper()}", time.time())
            pipe.execute()

    def volume(self) -> float:
        # noinspection PyUnresolvedReferences
        return redis.hincrbyfloat(self._name, f"{self.trade_symbol}_VOLUME", float(self.quantity))

    def volume_trades(self) -> tuple[float, float] | None:
        with redis.pipeline() as pipe:
            # noinspection PyUnresolvedReferences
            if self.is_seller is False:
                # noinspection PyUnresolvedReferences
                pipe.hincrbyfloat(
                    self._name,
                    f"{self.trade_symbol}_VOLUME_BUY_ORDERS",
                    float(self.quantity),
                )
                # noinspection PyUnresolvedReferences
                pipe.hget(self._name, f"{self.trade_symbol}_VOLUME_SELL_ORDERS")
            else:
                # noinspection PyUnresolvedReferences
                pipe.hget(self._name, f"{self.trade_symbol}_VOLUME_BUY_ORDERS")

                # noinspection PyUnresolvedReferences
                pipe.hincrbyfloat(
                    self._name,
                    f"{self.trade_symbol}_VOLUME_SELL_ORDERS",
                    float(self.quantity),
                )
            result = pipe.execute()

        try:
            result = float(result[0]), float(result[1])
        except TypeError:
            return None
        return result

    def number_trades(self) -> tuple[int, int] | None:
        with redis.pipeline() as pipe:
            # noinspection PyUnresolvedReferences
            if self.is_seller is False:
                # noinspection PyUnresolvedReferences
                pipe.hincrby(self._name, f"{self.trade_symbol}_NUMBER_BUY_ORDERS", 1)
                # noinspection PyUnresolvedReferences
                pipe.hget(self._name, f"{self.trade_symbol}_NUMBER_SELL_ORDERS")
            else:
                # noinspection PyUnresolvedReferences
                pipe.hget(self._name, f"{self.trade_symbol}_NUMBER_BUY_ORDERS")
                # noinspection PyUnresolvedReferences
                pipe.hincrby(self._name, f"{self.trade_symbol}_NUMBER_SELL_ORDERS", 1)
            result = pipe.execute()

        try:
            result = int(result[0]), int(result[1])
        except TypeError:
            return None
        return result
