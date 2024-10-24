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
            pipe.hset(f"PING", self.exchange.upper(), time.time())
            # noinspection PyUnresolvedReferences
            pipe.hset("PRICE", self.trade_symbol, float(self.price))
            pipe.execute()

    def volume(self) -> float:
        return redis.hincrbyfloat(self._name, f"{self.trade_symbol}_VOLUME", float(self.quantity))  # type: ignore

    def volume_trades(self) -> tuple[float, float] | None:
        with redis.pipeline() as pipe:
            if self.is_seller is False:  # type: ignore
                pipe.hincrbyfloat(
                    self._name,
                    f"{self.trade_symbol}_VOLUME_BUY_ORDERS",  # type: ignore
                    float(self.quantity),  # type: ignore
                )
                pipe.hget(self._name, f"{self.trade_symbol}_VOLUME_SELL_ORDERS")  # type: ignore
            else:
                pipe.hget(self._name, f"{self.trade_symbol}_VOLUME_BUY_ORDERS")  # type: ignore

                pipe.hincrbyfloat(
                    self._name,
                    f"{self.trade_symbol}_VOLUME_SELL_ORDERS",  # type: ignore
                    float(self.quantity),  # type: ignore
                )
            result = pipe.execute()

        try:
            result = float(result[0]), float(result[1])
        except TypeError:
            return None
        return result

    def number_trades(self) -> tuple[int, int] | None:
        with redis.pipeline() as pipe:
            if self.is_seller is False:  # type: ignore
                pipe.hincrby(self._name, f"{self.trade_symbol}_NUMBER_BUY_ORDERS", 1)  # type: ignore
                pipe.hget(self._name, f"{self.trade_symbol}_NUMBER_SELL_ORDERS")  # type: ignore
            else:
                pipe.hget(self._name, f"{self.trade_symbol}_NUMBER_BUY_ORDERS")  # type: ignore
                pipe.hincrby(self._name, f"{self.trade_symbol}_NUMBER_SELL_ORDERS", 1)  # type: ignore
            result = pipe.execute()

        try:
            result = int(result[0]), int(result[1])
        except TypeError:
            return None
        return result
